"""Risk manager (G2) — daily DD kill switch.

Logic:
- Đọc MT5 history_deals trong 24h gần nhất, tính tổng P&L
- Nếu P&L ≤ -kill_dd_pct% của balance → tạo flag file state/kill_switch.flag
- Mọi lệnh hunt/scan-once/run check flag đầu tiên → SKIP nếu killed
- Flag tự reset khi sang ngày mới (so timestamp với hôm nay UTC)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import MetaTrader5 as mt5

from xau_agent.config import ROOT, get_settings

log = logging.getLogger(__name__)

STATE_DIR = ROOT / "state"
KILL_FLAG = STATE_DIR / "kill_switch.flag"


@dataclass(frozen=True)
class RiskSnapshot:
    balance: float
    daily_pnl_usc: float
    daily_pnl_pct: float
    killed: bool
    kill_reason: str = ""


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def compute_daily_pnl(symbol: str | None = None) -> tuple[float, float, float]:
    """Tính P&L từ 00:00 UTC hôm nay tới giờ. Returns (balance, pnl_usc, pnl_pct).
    symbol=None → tất cả symbol; có symbol → chỉ filter symbol đó."""
    info = mt5.account_info()
    if info is None:
        log.warning("compute_daily_pnl: account_info None")
        return 0.0, 0.0, 0.0
    balance = float(info.balance)

    since = _today_utc_start()
    deals = mt5.history_deals_get(since, datetime.now(timezone.utc)) or []
    closing = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    if symbol:
        closing = [d for d in closing if d.symbol == symbol]
    pnl_usc = sum(d.profit for d in closing)
    pnl_pct = (pnl_usc / balance * 100.0) if balance else 0.0
    return balance, pnl_usc, pnl_pct


def is_killed() -> tuple[bool, str]:
    """Check flag file. Auto-reset nếu flag từ ngày cũ."""
    if not KILL_FLAG.exists():
        return False, ""
    try:
        content = KILL_FLAG.read_text(encoding="utf-8").strip()
        ts_line, _, reason = content.partition("|")
        flag_ts = datetime.fromisoformat(ts_line)
        if flag_ts.tzinfo is None:
            flag_ts = flag_ts.replace(tzinfo=timezone.utc)
        # Reset nếu flag đã qua >= 24h (sang ngày mới UTC)
        if flag_ts < _today_utc_start():
            log.info("kill switch auto-reset (flag from %s)", flag_ts.date())
            KILL_FLAG.unlink()
            return False, ""
        return True, reason.strip()
    except (OSError, ValueError) as e:
        log.warning("kill flag read error: %s", e)
        return False, ""


def arm_kill(reason: str) -> None:
    """Tạo flag file. Idempotent."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    KILL_FLAG.write_text(f"{ts}|{reason}", encoding="utf-8")
    log.warning("KILL SWITCH ARMED: %s", reason)


def reset_kill() -> bool:
    """Xóa flag thủ công. Return True nếu có flag để xóa."""
    if KILL_FLAG.exists():
        KILL_FLAG.unlink()
        log.info("kill switch reset (manual)")
        return True
    return False


def check_risk(symbol: str | None = None) -> RiskSnapshot:
    """Main entry — gọi đầu mỗi phiên hunt/scan-once.
    1. Check flag → nếu killed (chưa hết ngày), return killed=True ngay
    2. Tính P&L hôm nay → nếu vượt ngưỡng → arm kill, return killed=True
    3. Else return killed=False"""
    s = get_settings()
    killed, reason = is_killed()
    if killed:
        bal, pnl, pct = compute_daily_pnl(symbol)
        return RiskSnapshot(bal, pnl, pct, True, reason)

    balance, pnl_usc, pnl_pct = compute_daily_pnl(symbol)
    if pnl_pct <= -abs(s.kill_dd_pct):
        msg = f"daily DD {pnl_pct:.2f}% <= -{s.kill_dd_pct}% (PnL {pnl_usc:.2f} USC / balance {balance:.2f})"
        arm_kill(msg)
        return RiskSnapshot(balance, pnl_usc, pnl_pct, True, msg)
    return RiskSnapshot(balance, pnl_usc, pnl_pct, False, "")
