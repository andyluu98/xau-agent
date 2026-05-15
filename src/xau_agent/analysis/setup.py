"""M15 entry detection. Combines trend bias + momentum/oversold signals → Setup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from xau_agent.analysis.indicators import add_core_indicators

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Setup:
    side: Side
    entry: float
    sl: float
    tp: float
    atr: float
    rsi: float
    macd_hist: float
    reason: str


def _round(price: float, digits: int = 2) -> float:
    return round(price, digits)


def detect(
    m15: pd.DataFrame,
    trend_dir: Literal["UP", "DOWN", "FLAT"],
    atr_sl_mult: float = 1.5,
    atr_tp_mult: float = 2.5,
    atr_period: int = 14,
) -> Optional[Setup]:
    """Return a Setup if M15 confirms trend with momentum, else None.

    Logic (M15 must agree with trend_dir):
      UP   → close > EMA50, RSI 40-70, MACD hist > 0
      DOWN → close < EMA50, RSI 30-60, MACD hist < 0
    SL/TP = entry ± multiplier × ATR.
    """
    if trend_dir == "FLAT":
        return None

    df = add_core_indicators(m15, atr_period=atr_period)
    last = df.iloc[-1]
    if last[["EMA50", "RSI", "MACDh", "ATR"]].isna().any():
        return None

    close = float(last["close"])
    ema50 = float(last["EMA50"])
    rsi = float(last["RSI"])
    macdh = float(last["MACDh"])
    atr = float(last["ATR"])

    if trend_dir == "UP":
        ok = close > ema50 and 40 <= rsi <= 70 and macdh > 0
        side: Side = "BUY"
        sl = close - atr_sl_mult * atr
        tp = close + atr_tp_mult * atr
    else:  # DOWN
        ok = close < ema50 and 30 <= rsi <= 60 and macdh < 0
        side = "SELL"
        sl = close + atr_sl_mult * atr
        tp = close - atr_tp_mult * atr

    if not ok:
        return None

    return Setup(
        side=side,
        entry=_round(close),
        sl=_round(sl),
        tp=_round(tp),
        atr=_round(atr, 4),
        rsi=_round(rsi, 1),
        macd_hist=_round(macdh, 4),
        reason=f"{side} setup: close vs EMA50={close - ema50:+.2f}, RSI={rsi:.1f}, MACDh={macdh:+.4f}",
    )
