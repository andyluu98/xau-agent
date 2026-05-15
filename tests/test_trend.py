"""Smoke test trend.evaluate on synthetic OHLCV."""
from __future__ import annotations

import numpy as np
import pandas as pd

from xau_agent.analysis.trend import evaluate


def _synthetic(direction: str, n: int = 250, start: float = 2000.0) -> pd.DataFrame:
    """Build OHLCV that drifts up / down / flat so EMA50 and EMA200 line up cleanly."""
    rng = np.random.default_rng(42)
    if direction == "UP":
        drift = np.linspace(0, 50, n)
    elif direction == "DOWN":
        drift = np.linspace(0, -50, n)
    else:
        drift = np.zeros(n)
    noise = rng.normal(0, 0.5, n)
    close = start + drift + noise
    high = close + np.abs(rng.normal(0, 0.3, n))
    low = close - np.abs(rng.normal(0, 0.3, n))
    open_ = np.r_[close[0], close[:-1]]
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "tick_volume": 1},
        index=idx,
    )


def test_aligned_up() -> None:
    v = evaluate({"H1": _synthetic("UP"), "H4": _synthetic("UP")})
    assert v.aligned is True
    assert v.direction == "UP"


def test_aligned_down() -> None:
    v = evaluate({"H1": _synthetic("DOWN"), "H4": _synthetic("DOWN")})
    assert v.aligned is True
    assert v.direction == "DOWN"


def test_disagreed() -> None:
    v = evaluate({"H1": _synthetic("UP"), "H4": _synthetic("DOWN")})
    assert v.aligned is False
    assert v.direction == "FLAT"
