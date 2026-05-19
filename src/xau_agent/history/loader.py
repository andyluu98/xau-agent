"""Build a compact history brief from MT5 deals + journal CSV.

Used by `dayplan` (đưa context lịch sử cho Day Planner) và `plan-now`
(đưa context lịch sử cho 6 vai debate). Brief tóm tắt:
  - Win rate, loss patterns N ngày gần đây từ MT5 history
  - GO/SKIP gần đây từ journal CSV
  - Currently open positions/pending orders

Output là 1 chuỗi text gọn để inject vào prompt LLM (tránh JSON dump dài)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from xau_agent.journal import read_trades

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoryBrief:
    """Tóm tắt context lịch sử để feed vào prompt LLM."""
    text: str                       # nhiều dòng, để inject vào context
    closed_deals: int               # số deal đã đóng trong window
    wins: int
    losses: int
    net_pnl: float                  # đơn vị account (USC/USD)
    win_rate_pct: float
    open_positions: int
    pending_orders: int

    @property
    def has_data(self) -> bool:
        return self.closed_deals > 0 or self.open_positions > 0 or self.pending_orders > 0


def _fmt_mt5_deals(deals: list, currency: str) -> tuple[str, dict]:
    """Group MT5 deals by position_id để tính P/L per closed trade.
    Returns (text, stats)."""
    if not deals:
        return "", {"closed": 0, "wins": 0, "losses": 0, "net": 0.0}

    # Group by position_id, lấy deal OUT (entry=1)
    closed = [d for d in deals if d.entry == 1]
    wins = sum(1 for d in closed if d.profit > 0)
    losses = sum(1 for d in closed if d.profit < 0)
    net = sum(d.profit + d.commission + d.swap for d in deals)

    # Liệt kê tối đa 10 lệnh đóng gần nhất
    closed_sorted = sorted(closed, key=lambda d: d.time, reverse=True)[:10]
    lines = []
    for d in closed_sorted:
        ts = datetime.fromtimestamp(d.time).strftime("%m-%d %H:%M")
        side = "BUY_OUT" if d.type == 0 else "SELL_OUT"
        lines.append(f"  {ts}  {side}  {d.symbol}  vol={d.volume}  P/L={d.profit:+.2f}")

    stats = {"closed": len(closed), "wins": wins, "losses": losses, "net": net}
    text = (
        f"MT5 closed deals (gần 10 trên tổng {len(closed)} đã đóng):\n"
        + "\n".join(lines)
        + f"\nTotal net: {net:+.2f} {currency}  (W:{wins} L:{losses})"
    )
    return text, stats


def _fmt_open_positions(positions: list) -> tuple[str, int]:
    if not positions:
        return "", 0
    lines = ["Open positions HIỆN TẠI:"]
    for p in positions:
        # p.type: 0=BUY, 1=SELL
        side = "BUY" if p.type == 0 else "SELL"
        lines.append(
            f"  ticket={p.ticket}  {side}  {p.symbol}  vol={p.volume}  "
            f"open={p.price_open:.2f}  SL={p.sl:.2f}  TP={p.tp:.2f}  P/L={p.profit:+.2f}"
        )
    return "\n".join(lines), len(positions)


def _fmt_pending_orders(orders: list) -> tuple[str, int]:
    if not orders:
        return "", 0
    type_map = {2: "BUY_LIMIT", 3: "SELL_LIMIT", 4: "BUY_STOP", 5: "SELL_STOP"}
    lines = ["Pending orders HIỆN TẠI:"]
    for o in orders:
        lines.append(
            f"  ticket={o.ticket}  {type_map.get(o.type, str(o.type))}  {o.symbol}  "
            f"vol={o.volume_initial}  price={o.price_open:.2f}  SL={o.sl:.2f}  TP={o.tp:.2f}"
        )
    return "\n".join(lines), len(orders)


def _fmt_journal(rows: list[dict], limit: int) -> str:
    if not rows:
        return ""
    recent = rows[-limit:]
    lines = ["Journal CSV (N phiên hunt/scan gần nhất):"]
    for r in recent:
        ts = r.get("timestamp", "")[:16].replace("T", " ")
        side = r.get("side", "")
        judge = r.get("judge_decision", "")
        conf = r.get("judge_confidence", "")
        user = r.get("user_decision", "") or "-"
        bias = r.get("macro_bias", "")
        lines.append(
            f"  {ts}  {side}  judge={judge}({conf})  bias={bias}  user={user}"
        )
    return "\n".join(lines)


def build_brief(days: int = 7, journal_limit: int = 10) -> HistoryBrief:
    """Build history brief — không raise nếu MT5 chưa connect (graceful degrade).

    days: window cho MT5 history (chỉ deals trong N ngày gần)
    journal_limit: số entry journal CSV gần nhất để liệt kê
    """
    parts: list[str] = []
    closed = wins = losses = open_n = pending_n = 0
    net = 0.0
    currency = ""

    # 1) MT5 deals + open positions + pending
    try:
        import MetaTrader5 as mt5  # noqa: N813
        acc = mt5.account_info()
        if acc is not None:
            currency = acc.currency
            parts.append(
                f"Account: balance={acc.balance:.2f} {currency} equity={acc.equity:.2f}"
            )
            now = datetime.now()
            since = now - timedelta(days=days)
            deals = mt5.history_deals_get(since, now) or []
            text, stats = _fmt_mt5_deals(list(deals), currency)
            if text:
                parts.append(text)
                closed = stats["closed"]
                wins = stats["wins"]
                losses = stats["losses"]
                net = stats["net"]

            positions = list(mt5.positions_get() or [])
            text, open_n = _fmt_open_positions(positions)
            if text:
                parts.append(text)

            orders = list(mt5.orders_get() or [])
            text, pending_n = _fmt_pending_orders(orders)
            if text:
                parts.append(text)
    except Exception as e:  # noqa: BLE001
        log.debug("history_loader: MT5 unavailable, skipping (%s)", e)

    # 2) Journal CSV — luôn đọc được kể cả khi không có MT5
    try:
        rows = read_trades(limit=0)
        text = _fmt_journal(rows, journal_limit)
        if text:
            parts.append(text)
    except Exception as e:  # noqa: BLE001
        log.debug("history_loader: journal read failed (%s)", e)

    win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) else 0.0
    text_full = "\n\n".join(parts) if parts else "(no history available)"
    return HistoryBrief(
        text=text_full,
        closed_deals=closed,
        wins=wins,
        losses=losses,
        net_pnl=net,
        win_rate_pct=win_rate,
        open_positions=open_n,
        pending_orders=pending_n,
    )
