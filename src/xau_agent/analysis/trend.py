"""Multi-TF trend filter. Determines if H1 + H4 agree on direction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from xau_agent.analysis.indicators import ema

Direction = Literal["UP", "DOWN", "FLAT"]


@dataclass(frozen=True)
class TFTrend:
    tf: str
    direction: Direction
    close: float
    ema50: float
    ema200: float
    note: str


@dataclass(frozen=True)
class TrendVerdict:
    aligned: bool
    direction: Direction          # UP / DOWN if aligned, else FLAT
    per_tf: list[TFTrend]
    reason: str


def _classify(df: pd.DataFrame) -> tuple[Direction, float, float, float]:
    e50 = ema(df, 50).iloc[-1]
    e200 = ema(df, 200).iloc[-1]
    close = df["close"].iloc[-1]
    if pd.isna(e50) or pd.isna(e200):
        return "FLAT", float(close), float("nan"), float("nan")
    # Direction: price above both EMAs AND EMA50 > EMA200 → UP
    if close > e50 and close > e200 and e50 > e200:
        return "UP", float(close), float(e50), float(e200)
    if close < e50 and close < e200 and e50 < e200:
        return "DOWN", float(close), float(e50), float(e200)
    return "FLAT", float(close), float(e50), float(e200)


def evaluate(tf_data: dict[str, pd.DataFrame]) -> TrendVerdict:
    """Inspect each TF, return aligned verdict.

    tf_data: {"H1": df, "H4": df} — caller supplies needed TFs.
    Aligned iff every TF has same non-FLAT direction.
    """
    per_tf: list[TFTrend] = []
    dirs: set[Direction] = set()
    for tf, df in tf_data.items():
        d, close, e50, e200 = _classify(df)
        note = f"close={close:.2f} EMA50={e50:.2f} EMA200={e200:.2f}"
        per_tf.append(TFTrend(tf=tf, direction=d, close=close, ema50=e50, ema200=e200, note=note))
        dirs.add(d)

    if len(dirs) == 1 and "FLAT" not in dirs:
        direction = next(iter(dirs))
        return TrendVerdict(True, direction, per_tf, f"all TFs agree {direction}")
    detail = " | ".join(f"{t.tf}={t.direction}" for t in per_tf)
    return TrendVerdict(False, "FLAT", per_tf, f"TFs disagree: {detail}")
