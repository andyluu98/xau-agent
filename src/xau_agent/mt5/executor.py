"""Place / modify / close MT5 orders. Honors --dry-run flag."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import MetaTrader5 as mt5  # noqa: N813

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Literal["BUY", "SELL"]
    lot: float
    sl: float
    tp: float
    comment: str = "xau-agent"


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    ticket: int | None
    price: float | None
    retcode: int | None
    message: str


def _filling_mode(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    if info.filling_mode & mt5.SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    if info.filling_mode & mt5.SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def place(req: OrderRequest, dry_run: bool = True) -> OrderResult:
    """Send market order. If dry_run, log and return synthetic OK result."""
    if dry_run:
        log.info("[DRY-RUN] %s %s %.2f lot SL=%.2f TP=%.2f", req.side, req.symbol, req.lot, req.sl, req.tp)
        return OrderResult(ok=True, ticket=None, price=None, retcode=None, message="dry-run")

    tick = mt5.symbol_info_tick(req.symbol)
    if tick is None:
        return OrderResult(False, None, None, None, f"no tick: {mt5.last_error()}")
    price = tick.ask if req.side == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if req.side == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": req.symbol,
        "volume": req.lot,
        "type": order_type,
        "price": price,
        "sl": req.sl,
        "tp": req.tp,
        "deviation": 20,
        "magic": 26515,
        "comment": req.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(req.symbol),
    }
    result = mt5.order_send(request)
    if result is None:
        return OrderResult(False, None, None, None, f"order_send None: {mt5.last_error()}")
    ok = result.retcode == mt5.TRADE_RETCODE_DONE
    return OrderResult(
        ok=ok,
        ticket=result.order if ok else None,
        price=result.price if ok else None,
        retcode=result.retcode,
        message=result.comment or "",
    )


def count_open_positions(symbol: str) -> int:
    positions = mt5.positions_get(symbol=symbol)
    return 0 if positions is None else len(positions)


def calc_lot_by_risk(
    symbol: str, balance: float, sl_distance_price: float, risk_pct: float,
) -> float | None:
    """Tính lot sao cho khi chạm SL chỉ lỗ `risk_pct`% balance.

    sl_distance_price: khoảng cách entry → SL tính theo PRICE (vd 2.0 cho XAUUSD)
    risk_pct: % balance chấp nhận lỗ (vd 1.0 = 1%)

    Returns lot (đã round xuống bội số volume_step, clamp min/max). None nếu không tính được.
    """
    if risk_pct <= 0 or sl_distance_price <= 0:
        return None
    info = mt5.symbol_info(symbol)
    if info is None:
        log.warning("calc_lot_by_risk: symbol_info(%s) None", symbol)
        return None

    tick_size = float(info.trade_tick_size or 0.001)
    tick_value = float(info.trade_tick_value or 0.0)
    if tick_size <= 0 or tick_value <= 0:
        log.warning("calc_lot_by_risk: bad tick_size=%s tick_value=%s", tick_size, tick_value)
        return None

    # Loss per 1 lot khi chạm SL
    loss_per_lot = (sl_distance_price / tick_size) * tick_value
    if loss_per_lot <= 0:
        return None

    target_loss = balance * risk_pct / 100.0
    raw_lot = target_loss / loss_per_lot

    step = float(info.volume_step or 0.01)
    vmin = float(info.volume_min or step)
    vmax = float(info.volume_max or 100.0)

    # Round xuống bội số step để không vượt risk
    lot = (int(raw_lot / step)) * step
    lot = max(vmin, min(vmax, lot))
    return round(lot, 2)
