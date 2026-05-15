"""Fetch OHLCV bars from MT5 for any timeframe. Returns pandas DataFrame."""
from __future__ import annotations

import logging
from typing import Final

import MetaTrader5 as mt5  # noqa: N813
import pandas as pd

log = logging.getLogger(__name__)

TF_MAP: Final[dict[str, int]] = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class FetchError(RuntimeError):
    """Raised when MT5 returns no bars."""


def fetch_bars(symbol: str, tf: str, count: int = 200) -> pd.DataFrame:
    """Fetch `count` most recent closed bars for `symbol` at `tf`.

    Returns DataFrame indexed by UTC time with columns: open, high, low, close, tick_volume.
    """
    tf_code = TF_MAP.get(tf.upper())
    if tf_code is None:
        raise ValueError(f"Unsupported timeframe: {tf}")

    if not mt5.symbol_select(symbol, True):
        raise FetchError(f"symbol_select({symbol}) failed: {mt5.last_error()}")

    rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, count)
    if rates is None or len(rates) == 0:
        raise FetchError(f"No bars returned for {symbol} {tf}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    df = df[["open", "high", "low", "close", "tick_volume"]]
    return df


def fetch_multi_tf(symbol: str, tfs: list[str], count: int = 200) -> dict[str, pd.DataFrame]:
    """Fetch multiple timeframes at once. Returns dict keyed by TF name."""
    return {tf: fetch_bars(symbol, tf, count) for tf in tfs}


def current_price(symbol: str) -> tuple[float, float]:
    """Return (bid, ask) for symbol."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise FetchError(f"No tick for {symbol}: {mt5.last_error()}")
    return tick.bid, tick.ask
