"""Indicator wrappers. Thin layer over pandas-ta + pandas so the rest of the code
   never touches indicator libs directly."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta


def ema(df: pd.DataFrame, length: int) -> pd.Series:
    return ta.ema(df["close"], length=length)


def rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return ta.rsi(df["close"], length=length)


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Returns columns: MACD, MACDh (hist), MACDs (signal)."""
    out = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    out.columns = ["MACD", "MACDh", "MACDs"]
    return out


def bbands(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands. Returns BBL (lower), BBM (mid), BBU (upper), BBB, BBP."""
    out = ta.bbands(df["close"], length=length, std=std)
    out.columns = ["BBL", "BBM", "BBU", "BBB", "BBP"]
    return out


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return ta.atr(df["high"], df["low"], df["close"], length=length)


def add_core_indicators(df: pd.DataFrame, atr_period: int = 14) -> pd.DataFrame:
    """Augment OHLCV df with EMA50/200, RSI14, MACD, BB, ATR. Returns new df."""
    out = df.copy()
    out["EMA50"] = ema(df, 50)
    out["EMA200"] = ema(df, 200)
    out["RSI"] = rsi(df, 14)
    out = out.join(macd(df))
    out = out.join(bbands(df))
    out["ATR"] = atr(df, atr_period)
    return out


def last_row(df: pd.DataFrame) -> dict:
    """Return last row as plain dict with NaN→None for JSON-friendliness."""
    row = df.iloc[-1].to_dict()
    return {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in row.items()}
