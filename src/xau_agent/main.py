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
from xau_agent.external import tradingview_ta as tv
from xau_agent.journal import (
    TradeRecord, log_trade, parse_macro_bias_strength, summarize,
)
from xau_agent.llm import agents as llm_agents
from xau_agent.llm import execution as llm_exec
from xau_agent.mt5 import connector, executor, fetcher
from xau_agent.news import tavily
from xau_agent.risk_manager import check_risk, reset_kill

log = logging.getLogger("xau_agent")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _resolve_lot(symbol: str, sl_price_distance: float, lot_multiplier: float = 1.0) -> float:
    """Tính lot cuối:
    - Nếu risk_pct_per_trade > 0 → dùng risk-based (G3)
    - Else → default_lot
    - Nhân lot_multiplier từ Execution Trader (vai #7)
    - Clamp về default_lot nếu tính lỗi"""
    s = get_settings()
    base = s.default_lot
    if s.risk_pct_per_trade > 0 and sl_price_distance > 0:
        info = mt5_account_balance()
        if info is not None:
            calc = executor.calc_lot_by_risk(symbol, info, sl_price_distance, s.risk_pct_per_trade)
            if calc and calc > 0:
                base = calc
    return round(base * (lot_multiplier or 1.0), 2) or s.default_lot


def mt5_account_balance() -> float | None:
    """Lấy balance hiện tại (tách hàm để dễ mock trong test)."""
    import MetaTrader5 as mt5
    info = mt5.account_info()
    return float(info.balance) if info else None


def _kill_gate(symbol: str) -> bool:
    """Check kill switch trước khi chạy phiên. Returns True nếu bị block."""
    snap = check_risk(symbol)
    if snap.killed:
        display.render_skip(
            f"KILL SWITCH active — daily DD {snap.daily_pnl_pct:.2f}%",
            f"PnL hôm nay: {snap.daily_pnl_usc:+.2f} USC · {snap.kill_reason}\n"
            f"Tự reset 00:00 UTC. Reset thủ công: xau-agent reset-kill",
        )
        return True
    return False


def _news_blackout_gate() -> bool:
    """G5: check sắp có tin lớn không. Returns True nếu bị block."""
    s = get_settings()
    if not s.news_blackout_enabled:
        return False
    is_blackout, reason = tavily.detect_blackout()
    if is_blackout:
        display.render_skip(
            "NEWS BLACKOUT — sắp có tin lớn",
            f"{reason}\nTắt G5 tạm: NEWS_BLACKOUT_ENABLED=false trong .env",
        )
        return True
    return False


def _build_record(
    su, verdict, result, plan, tv_map, news,
    user_decision: str, ticket: int, lot: float, dry_run: bool,
) -> TradeRecord:
    """Tổng hợp toàn bộ context phiên săn → TradeRecord để log."""
    bias, strength = parse_macro_bias_strength(result.macro)
    h1 = next((t.direction for t in verdict.per_tf if t.tf == "H1"), "")
    h4 = next((t.direction for t in verdict.per_tf if t.tf == "H4"), "")
    m15c = tv_map.get("M15")
    h1c = tv_map.get("H1")
    h4c = tv_map.get("H4")
    return TradeRecord(
        ticket=ticket,
        side=su.side, entry=su.entry, sl=su.sl, tp=su.tp, lot=lot,
        atr=su.atr, rsi=su.rsi, macd_hist=su.macd_hist,
        trend_h1=h1, trend_h4=h4,
        tv_m15_reco=m15c.recommendation if m15c else "",
        tv_h1_reco=h1c.recommendation if h1c else "",
        tv_h4_reco=h4c.recommendation if h4c else "",
        news_tldr=summarize(news),
        bull_summary=summarize(result.bull),
        bear_summary=summarize(result.bear),
        macro_bias=bias, macro_strength=strength,
        judge_decision=result.verdict.decision,
        judge_confidence=result.verdict.confidence,
        judge_summary=result.verdict.summary,
        exec_strategy=plan.entry_strategy if plan else "",
        exec_lot_mul=plan.lot_multiplier if plan else 1.0,
        exec_hold_rule=plan.hold_rule if plan else "",
        user_decision=user_decision,
        dry_run=dry_run,
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

    # Kill switch (G2) — first gate, before anything else
    if _kill_gate(s.symbol):
        return

    # News blackout (G5) — skip nếu sắp có FOMC/CPI/NFP
    if _news_blackout_gate():
        return

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

    # News + TV consensus + 6-vai debate
    news = tavily.brief()
    tv_map = tv.fetch_consensus(s.tv_symbol, s.tv_exchange, s.tv_screener, [s.entry_tf] + s.trend_tf_list)
    display.render_tv_consensus(tv_map)
    result = llm_agents.run_debate(asdict(su), _trend_to_dict(verdict), news, tv=tv.to_dict(tv_map))
    display.render_proposal(su, result, news, s.default_lot)

    if result.verdict.decision != "GO":
        # Final verdict panel đã render trong render_proposal (🎯 KẾT LUẬN), không cần render_skip dư.
        log_trade(_build_record(su, verdict, result, None, tv_map, news,
                                user_decision="", ticket=0, lot=s.default_lot, dry_run=dry_run))
        return

    # Execution Trader (vai #7): thiết kế entry plan
    plan = llm_exec.design_execution(
        asdict(su), _trend_to_dict(verdict), news, tv.to_dict(tv_map),
        result.macro, result.verdict.summary,
    )
    display.render_execution_plan(plan, s.default_lot)
    sl_dist = abs(su.entry - su.sl)
    final_lot = _resolve_lot(s.symbol, sl_dist, plan.lot_multiplier)

    # Human gate
    choice = prompt.ask_approval()
    if choice != "YES":
        display.render_skip(f"user said {choice}")
        log_trade(_build_record(su, verdict, result, plan, tv_map, news,
                                user_decision=choice, ticket=0, lot=final_lot, dry_run=dry_run))
        return

    # Execute (or dry-run) — dùng lot từ Execution Trader
    req = executor.OrderRequest(
        symbol=s.symbol, side=su.side, lot=final_lot, sl=su.sl, tp=su.tp,
    )
    res = executor.place(req, dry_run=dry_run)
    display.render_result(res.ok, res.message, res.ticket, res.price)
    log_trade(_build_record(su, verdict, result, plan, tv_map, news,
                            user_decision="YES", ticket=res.ticket or 0,
                            lot=final_lot, dry_run=dry_run))


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


def _hunt_once(side_override: str | None, dry_run_override: bool | None = None) -> None:
    """Hunt mode: force-build setup (bypass strict M15 gate), always run LLM debate.
    If trend aligned and side_override=None, use trend direction. If trend FLAT, require side_override."""
    s = get_settings()
    dry_run = s.dry_run if dry_run_override is None else dry_run_override
    display.banner(s.symbol, s.entry_tf, s.trend_tf_list, dry_run)

    if _kill_gate(s.symbol):
        return

    if _news_blackout_gate():
        return

    all_tfs = [s.entry_tf] + s.trend_tf_list
    data = fetcher.fetch_multi_tf(s.symbol, all_tfs, count=s.bars_lookback)
    verdict = trend_mod.evaluate({tf: data[tf] for tf in s.trend_tf_list})
    display.render_trend(verdict.per_tf)

    # Decide side
    if side_override:
        side = side_override.upper()
    elif verdict.aligned:
        side = "BUY" if verdict.direction == "UP" else "SELL"
    else:
        display.render_skip("trend not aligned and no --side override", verdict.reason)
        return
    if side not in ("BUY", "SELL"):
        display.render_skip(f"invalid side: {side}")
        return

    su = setup_mod.build_forced(
        data[s.entry_tf], side,  # type: ignore[arg-type]
        atr_sl_mult=s.atr_sl_mult, atr_tp_mult=s.atr_tp_mult, atr_period=s.atr_period,
    )

    news = tavily.brief()
    tv_map = tv.fetch_consensus(s.tv_symbol, s.tv_exchange, s.tv_screener, [s.entry_tf] + s.trend_tf_list)
    display.render_tv_consensus(tv_map)
    result = llm_agents.run_debate(asdict(su), _trend_to_dict(verdict), news, tv=tv.to_dict(tv_map))
    display.render_proposal(su, result, news, s.default_lot)

    if result.verdict.decision != "GO":
        # Final verdict panel đã render trong render_proposal (🎯 KẾT LUẬN), không cần render_skip dư.
        log_trade(_build_record(su, verdict, result, None, tv_map, news,
                                user_decision="", ticket=0, lot=s.default_lot, dry_run=dry_run))
        return

    plan = llm_exec.design_execution(
        asdict(su), _trend_to_dict(verdict), news, tv.to_dict(tv_map),
        result.macro, result.verdict.summary,
    )
    display.render_execution_plan(plan, s.default_lot)
    sl_dist = abs(su.entry - su.sl)
    final_lot = _resolve_lot(s.symbol, sl_dist, plan.lot_multiplier)

    choice = prompt.ask_approval()
    if choice != "YES":
        display.render_skip(f"user said {choice}")
        log_trade(_build_record(su, verdict, result, plan, tv_map, news,
                                user_decision=choice, ticket=0, lot=final_lot, dry_run=dry_run))
        return

    req = executor.OrderRequest(symbol=s.symbol, side=su.side, lot=final_lot, sl=su.sl, tp=su.tp)
    res = executor.place(req, dry_run=dry_run)
    display.render_result(res.ok, res.message, res.ticket, res.price)
    log_trade(_build_record(su, verdict, result, plan, tv_map, news,
                            user_decision="YES", ticket=res.ticket or 0,
                            lot=final_lot, dry_run=dry_run))


def _cmd_hunt(args: argparse.Namespace) -> None:
    with connector.session():
        _hunt_once(side_override=args.side, dry_run_override=(not args.live))


def _cmd_plan(args: argparse.Namespace) -> None:
    from xau_agent.cli.plan import show_plan
    show_plan()


def _cmd_journal(args: argparse.Namespace) -> None:
    from xau_agent.cli.journal_display import render_recent
    render_recent(limit=args.limit)


def _cmd_reset_kill(args: argparse.Namespace) -> None:
    removed = reset_kill()
    if removed:
        display.render_skip("Kill switch ĐÃ RESET — bot có thể trade lại")
    else:
        display.render_skip("Kill switch chưa active, không có gì để reset")


def _cmd_tv(args: argparse.Namespace) -> None:
    """In TradingView 26-indicator consensus cho M15/H1/H4 (không gọi LLM, không MT5)."""
    s = get_settings()
    tfs = [s.entry_tf] + s.trend_tf_list
    log.info("Fetching TV consensus for %s on %s (%s) tfs=%s", s.tv_symbol, s.tv_exchange, s.tv_screener, tfs)
    tv_map = tv.fetch_consensus(s.tv_symbol, s.tv_exchange, s.tv_screener, tfs, force_refresh=args.refresh)
    display.render_tv_consensus(tv_map)


def _cmd_zones(args: argparse.Namespace) -> None:
    """In các vùng mua/bán quan trọng từ MT5 data, không gọi LLM."""
    from xau_agent.analysis import zones as zones_mod
    from xau_agent.cli.zones_display import render_zones

    s = get_settings()
    with connector.session():
        data = fetcher.fetch_multi_tf(s.symbol, ["M15", "H1", "H4"], count=s.bars_lookback)
        bid, ask = fetcher.current_price(s.symbol)
        mid = (bid + ask) / 2
        zlist = zones_mod.detect(data["M15"], data["H1"], data["H4"], mid, atr_period=s.atr_period)
        render_zones(s.symbol, mid, zlist, top_n=6)


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

    p_hunt = sub.add_parser(
        "hunt",
        help="HUNT mode: bypass strict M15 gate, force full LLM debate. Auto-pick side from H1+H4 trend, or use --side BUY/SELL.",
    )
    p_hunt.add_argument("--side", choices=["BUY", "SELL"], default=None,
                        help="force side; if omitted and trend aligned, uses trend direction")
    p_hunt.add_argument("--live", action="store_true", help="disable dry-run")
    p_hunt.set_defaults(func=_cmd_hunt)

    p_plan = sub.add_parser("plan", help="in plan san vang (chien luoc M15) ngay tren CLI")
    p_plan.set_defaults(func=_cmd_plan)

    p_zones = sub.add_parser("zones", help="quet MT5 va in cac vung MUA/BAN quan trong (S/R, EMA, swing, mocl tron)")
    p_zones.set_defaults(func=_cmd_zones)

    p_tv = sub.add_parser("tv", help="in TradingView 26-indicator consensus (free, no auth)")
    p_tv.add_argument("--refresh", action="store_true", help="bypass cache 5min")
    p_tv.set_defaults(func=_cmd_tv)

    p_journal = sub.add_parser("journal", help="in N lenh gan nhat tu so tay CSV (state/trades.csv)")
    p_journal.add_argument("--limit", type=int, default=10, help="so dong de in (default 10)")
    p_journal.set_defaults(func=_cmd_journal)

    p_reset = sub.add_parser("reset-kill", help="xoa flag kill switch (G2) thu cong")
    p_reset.set_defaults(func=_cmd_reset_kill)

    args = parser.parse_args()
    s = get_settings()
    _setup_logging(args.log_level or s.log_level)
    args.func(args)


if __name__ == "__main__":
    cli()
