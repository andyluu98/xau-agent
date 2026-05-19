"""Trade journal (G1) — append-only CSV log mỗi lệnh để review sau.

Mỗi lần `executor.place()` thành công (kể cả dry-run), bot log 1 dòng vào
`state/trades.csv` với toàn bộ context: setup, trend, news, TV consensus,
6 vai output, judge verdict, execution plan, user decision.

Đây là input cho:
- G8 Memory Agent (đọc 20 lệnh gần nhất → feed Judge)
- G9 Stats Dashboard (win-rate, PF, RR analysis)
- G14 EOD Reflection (cuối ngày AI tự rút bài học)
"""
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from xau_agent.config import ROOT

log = logging.getLogger(__name__)

STATE_DIR = ROOT / "state"
TRADES_CSV = STATE_DIR / "trades.csv"


@dataclass
class TradeRecord:
    timestamp: str = ""
    ticket: int = 0
    side: str = ""              # BUY | SELL
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    lot: float = 0.0
    atr: float = 0.0
    rsi: float = 0.0
    macd_hist: float = 0.0
    trend_h1: str = ""          # UP | DOWN | FLAT
    trend_h4: str = ""
    tv_m15_reco: str = ""       # STRONG_BUY/BUY/NEUTRAL/SELL/STRONG_SELL
    tv_h1_reco: str = ""
    tv_h4_reco: str = ""
    news_tldr: str = ""         # first 150 chars
    bull_summary: str = ""      # first 150 chars
    bear_summary: str = ""      # first 150 chars
    macro_bias: str = ""        # BULL | BEAR | FLAT (parsed from macro analyst output)
    macro_strength: str = ""    # "7/10"
    judge_decision: str = ""    # GO | SKIP
    judge_confidence: int = 0
    judge_summary: str = ""
    exec_strategy: str = ""     # now | pullback_ema20 | breakout_X
    exec_lot_mul: float = 1.0
    exec_hold_rule: str = ""    # to_tp | close_before_news | trail_after_1atr | be_at_1atr
    user_decision: str = ""     # YES | NO | SKIP | "" if Judge SKIP'd
    exit_time: str = ""         # filled later by trade_monitor (G6)
    exit_price: float = 0.0
    pnl_usc: float = 0.0
    hold_minutes: int = 0
    dry_run: bool = True


def _ensure_csv() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not TRADES_CSV.exists():
        with open(TRADES_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([fld.name for fld in fields(TradeRecord)])


def log_trade(record: TradeRecord) -> None:
    """Append 1 dòng vào state/trades.csv. Tạo file + header nếu chưa có."""
    _ensure_csv()
    if not record.timestamp:
        record.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([getattr(record, fld.name) for fld in fields(TradeRecord)])
        log.info("journal: logged trade %s %s @ %.2f (judge=%s)",
                 record.side, record.ticket or "dry", record.entry, record.judge_decision)
    except OSError as e:
        log.error("journal write failed: %s", e)


def read_trades(limit: int = 0) -> list[dict]:
    """Đọc CSV → list of dict. limit=0 → đọc hết. Trả về [] nếu chưa có file."""
    if not TRADES_CSV.exists():
        return []
    with open(TRADES_CSV, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-limit:] if limit > 0 else rows


_BIAS_RE = re.compile(r"BIAS\s*=\s*(\w+)\s+STRENGTH\s*=\s*(\d+/\d+)", re.IGNORECASE)


def parse_macro_bias_strength(macro_text: str) -> tuple[str, str]:
    """Macro Analyst kết thúc với 'BIAS=BULL|BEAR|FLAT STRENGTH=N/10'. Parse ra tuple.
    Chỉ match strength dạng số/số (vd 7/10), tránh dính markdown ** đuôi."""
    if not macro_text:
        return "", ""
    m = _BIAS_RE.search(macro_text)
    return (m.group(1).upper(), m.group(2)) if m else ("", "")


def summarize(text: str, max_len: int = 150) -> str:
    """Cắt text dài về max_len ký tự, replace newlines = space, thêm '...' nếu cắt."""
    if not text:
        return ""
    s = " ".join(text.split())
    return s if len(s) <= max_len else s[: max_len - 3] + "..."
