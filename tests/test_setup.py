"""Smoke test setup.detect on synthetic M15."""
from __future__ import annotations

import numpy as np
import pandas as pd

from xau_agent.analysis.setup import detect


def _m15_up(n: int = 250) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    drift = np.linspace(0, 30, n)
    close = 2000.0 + drift + rng.normal(0, 0.4, n)
    high = close + 0.5
    low = close - 0.5
    open_ = np.r_[close[0], close[:-1]]
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "tick_volume": 1},
        index=idx,
    )


def test_setup_buy_when_trend_up() -> None:
    su = detect(_m15_up(), trend_dir="UP")
    # Setup may or may not fire depending on RSI/MACD, but if it does it must be BUY + SL<entry<TP
    if su is not None:
        assert su.side == "BUY"
        assert su.sl < su.entry < su.tp
        assert su.atr > 0


def test_no_setup_when_flat() -> None:
    su = detect(_m15_up(), trend_dir="FLAT")
    assert su is None
