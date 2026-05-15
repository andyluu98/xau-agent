"""xau-agent CLI entry. Subcommands: run (loop), scan-once (single pass)."""
from __future__ import annotations

import argparse
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone

from xau_agent.analysis import setup as setup_mod
from xau_agent.analysis import trend as trend_mod
from xau_agent.cli import display, prompt
from xau_agent.config import get_settings
from xau_agent.llm import agents as llm_agents
from xau_agent.mt5 import connector, executor, fetcher
from xau_agent.news import tavily

log = logging.getLogger("xau_agent")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _trend_to_dict(verdict) -> dict:
    return {
        "aligned": verdict.aligned,
        "direction": verdict.direction,
        "reason": verdict.reason,
        "per_tf": [
            {"tf": t.tf, "direction": t.direction, "close": t.close, "ema50": t.ema50, "ema200": t.ema200}
            for t in verdict.per_tf
        ],
    }


def _scan_once(dry_run_override: bool | None = None) -> None:
    """One scan cycle: fetch → trend → setup → news → debate → prompt → execute."""
    s = get_settings()
    dry_run = s.dry_run if dry_run_override is None else dry_run_override
    display.banner(s.symbol, s.entry_tf, s.trend_tf_list, dry_run)

    # Daily trade cap
    open_n = executor.count_open_positions(s.symbol)
    if open_n >= s.max_open_trades:
        display.render_skip(f"max_open_trades reached ({open_n}/{s.max_open_trades})")
        return

    # Fetch M15 + trend TFs
    all_tfs = [s.entry_tf] + s.trend_tf_list
    data = fetcher.fetch_multi_tf(s.symbol, all_tfs, count=s.bars_lookback)

    # Trend filter
    trend_data = {tf: data[tf] for tf in s.trend_tf_list}
    verdict = trend_mod.evaluate(trend_data)
    display.render_trend(verdict.per_tf)
    if not verdict.aligned:
        display.render_skip("trend not aligned", verdict.reason)
        return

    # M15 setup
    su = setup_mod.detect(
        data[s.entry_tf], verdict.direction,
        atr_sl_mult=s.atr_sl_mult, atr_tp_mult=s.atr_tp_mult, atr_period=s.atr_period,
    )
    if su is None:
        display.render_skip("no M15 setup confirms trend", f"trend={verdict.direction}")
        return

    # News + debate
    news = tavily.brief()
    bull, bear, jv = llm_agents.run_debate(asdict(su), _trend_to_dict(verdict), news)
    display.render_proposal(su, jv, bull, bear, news, s.default_lot)

    if jv.decision != "GO":
        display.render_skip(f"judge SKIP (confidence={jv.confidence})")
        return

    # Human gate
    choice = prompt.ask_approval()
    if choice != "YES":
        display.render_skip(f"user said {choice}")
        return

    # Execute (or dry-run)
    req = executor.OrderRequest(
        symbol=s.symbol, side=su.side, lot=s.default_lot, sl=su.sl, tp=su.tp,
    )
    res = executor.place(req, dry_run=dry_run)
    display.render_result(res.ok, res.message, res.ticket, res.price)


def _wait_next_m15_close() -> None:
    """Sleep until next M15 boundary + 5s buffer."""
    now = datetime.now(timezone.utc)
    minute = (now.minute // 15 + 1) * 15
    extra_hours, minute = divmod(minute, 60)
    target = now.replace(minute=minute % 60, second=5, microsecond=0)
    target = target.replace(hour=(now.hour + extra_hours) % 24)
    delta = (target - now).total_seconds()
    if delta < 0:
        delta += 15 * 60
    log.info("sleep %.1fs until next M15 close", delta)
    time.sleep(delta)


def _cmd_run(args: argparse.Namespace) -> None:
    while True:
        try:
            with connector.session():
                _scan_once(dry_run_override=(not args.live))
        except KeyboardInterrupt:
            log.info("interrupted by user")
            return
        except Exception as e:  # noqa: BLE001
            log.exception("scan failed: %s", e)
        _wait_next_m15_close()


def _cmd_scan_once(args: argparse.Namespace) -> None:
    with connector.session():
        _scan_once(dry_run_override=(not args.live))


def cli() -> None:
    parser = argparse.ArgumentParser(prog="xau-agent", description="Semi-auto AI trader for XAUUSD M15")
    parser.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="continuous loop, scans on every M15 close")
    p_run.add_argument("--live", action="store_true", help="disable dry-run (send real orders)")
    p_run.set_defaults(func=_cmd_run)

    p_once = sub.add_parser("scan-once", help="single scan-propose-execute cycle then exit")
    p_once.add_argument("--live", action="store_true", help="disable dry-run")
    p_once.set_defaults(func=_cmd_scan_once)

    args = parser.parse_args()
    s = get_settings()
    _setup_logging(args.log_level or s.log_level)
    args.func(args)


if __name__ == "__main__":
    cli()
