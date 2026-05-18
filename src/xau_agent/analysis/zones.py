"""Detect key support / resistance zones from recent OHLCV.

Cách tìm:
1. Swing high/low — đỉnh/đáy cục bộ trong N nến gần đây
2. EMA20/50/200 — vùng động (dynamic S/R)
3. Round numbers — mốc tâm lý (chia hết 50/100 điểm)
4. Recent high/low — đỉnh/đáy gần nhất (1 hôm, 1 tuần)

Gom các mức gần nhau (trong X ATR) thành 1 vùng. Trả về list xếp theo distance từ giá hiện tại.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from xau_agent.analysis.indicators import ema, atr

ZoneType = Literal["swing_high", "swing_low", "ema", "round", "recent_high", "recent_low"]


@dataclass(frozen=True)
class Zone:
    price: float
    kind: ZoneType
    tf: str        # "M15" / "H1" / "H4"
    note: str
    distance: float  # pip cách giá hiện tại; >0 = trên giá, <0 = dưới

    @property
    def side(self) -> Literal["above", "below"]:
        return "above" if self.distance > 0 else "below"


def _find_swings(df: pd.DataFrame, lookback: int = 3) -> tuple[list[float], list[float]]:
    """Tìm swing high/low bằng cửa sổ 2*lookback+1 nến. Bar giữa cao/thấp nhất → swing."""
    highs, lows = [], []
    n = len(df)
    if n < 2 * lookback + 1:
        return highs, lows
    for i in range(lookback, n - lookback):
        window_h = df["high"].iloc[i - lookback : i + lookback + 1]
        window_l = df["low"].iloc[i - lookback : i + lookback + 1]
        if df["high"].iloc[i] == window_h.max():
            highs.append(float(df["high"].iloc[i]))
        if df["low"].iloc[i] == window_l.min():
            lows.append(float(df["low"].iloc[i]))
    return highs, lows


def _round_levels(price: float, step: float = 50.0, count: int = 3) -> list[float]:
    """Mốc tròn gần giá hiện tại. step=50 nghĩa là 4500, 4550, 4600..."""
    base = round(price / step) * step
    return [base + i * step for i in range(-count, count + 1)]


def detect(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    current_price: float,
    atr_period: int = 14,
) -> list[Zone]:
    """Quét 3 khung, trả về list Zone đã loại trùng + xếp theo distance."""
    raw: list[Zone] = []

    # 1) Swing high/low từng khung
    for tf_name, df, swing_lookback in [("M15", m15, 3), ("H1", h1, 3), ("H4", h4, 2)]:
        highs, lows = _find_swings(df, lookback=swing_lookback)
        # giữ 3 swing gần nhất mỗi loại
        for h in highs[-3:]:
            raw.append(Zone(h, "swing_high", tf_name, "đỉnh cục bộ", h - current_price))
        for low in lows[-3:]:
            raw.append(Zone(low, "swing_low", tf_name, "đáy cục bộ", low - current_price))

    # 2) EMA động
    for tf_name, df in [("H1", h1), ("H4", h4)]:
        for period in (20, 50, 200):
            val = ema(df, period).iloc[-1]
            if pd.notna(val):
                raw.append(Zone(float(val), "ema", tf_name, f"EMA{period}", float(val) - current_price))

    # 3) Recent high/low (1 tuần ~ 168 nến H1)
    if len(h1) >= 100:
        hh = float(h1["high"].iloc[-168:].max())
        ll = float(h1["low"].iloc[-168:].min())
        raw.append(Zone(hh, "recent_high", "H1", "đỉnh 7 ngày", hh - current_price))
        raw.append(Zone(ll, "recent_low", "H1", "đáy 7 ngày", ll - current_price))

    # 4) Round numbers
    atr_val = float(atr(h1, atr_period).iloc[-1])
    for r in _round_levels(current_price, step=50.0, count=3):
        raw.append(Zone(r, "round", "—", "mốc tròn 50", r - current_price))

    # 5) Gom các zone gần nhau (chênh < 0.3 × ATR_H1) thành 1
    raw.sort(key=lambda z: z.price)
    merge_threshold = 0.3 * atr_val
    merged: list[Zone] = []
    for z in raw:
        if merged and abs(z.price - merged[-1].price) < merge_threshold:
            # giữ zone với note dài hơn (nhiều thông tin hơn)
            kept = merged[-1] if len(merged[-1].note) >= len(z.note) else z
            merged[-1] = kept
        else:
            merged.append(z)

    # 6) Sort by distance from current price (gần nhất trước)
    merged.sort(key=lambda z: abs(z.distance))
    return merged
