"""TradingView Technical Analysis consensus (free, no auth).

Dùng package tradingview-ta scrape widget public của TradingView,
trả về điểm consensus 26-indicator: STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL.

Mục đích trong xau-agent: thêm 1 phiếu vote bên ngoài (ngoài DeepSeek) cho Judge AI."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Final

from tradingview_ta import Interval, TA_Handler

log = logging.getLogger(__name__)

# Map khung thời gian xau-agent → tradingview_ta Interval enum
_TF_MAP: Final[dict[str, str]] = {
    "M1": Interval.INTERVAL_1_MINUTE,
    "M5": Interval.INTERVAL_5_MINUTES,
    "M15": Interval.INTERVAL_15_MINUTES,
    "M30": Interval.INTERVAL_30_MINUTES,
    "H1": Interval.INTERVAL_1_HOUR,
    "H2": Interval.INTERVAL_2_HOURS,
    "H4": Interval.INTERVAL_4_HOURS,
    "D1": Interval.INTERVAL_1_DAY,
    "W1": Interval.INTERVAL_1_WEEK,
}

CACHE_TTL_S = 300  # 5 phút


@dataclass(frozen=True)
class TVConsensus:
    tf: str                       # "M15"
    recommendation: str           # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
    buy: int
    sell: int
    neutral: int
    oscillators_reco: str         # rating tách riêng cho nhóm oscillator
    moving_averages_reco: str     # rating tách riêng cho nhóm MA

    @property
    def total_votes(self) -> int:
        return self.buy + self.sell + self.neutral

    @property
    def bias(self) -> str:
        """Bias rút gọn: UP / DOWN / FLAT."""
        if "BUY" in self.recommendation:
            return "UP"
        if "SELL" in self.recommendation:
            return "DOWN"
        return "FLAT"


@dataclass
class _Cache:
    data: dict[tuple, TVConsensus] = field(default_factory=dict)
    ts: dict[tuple, float] = field(default_factory=dict)


_cache = _Cache()


def _fetch_one(symbol: str, exchange: str, screener: str, tf: str) -> TVConsensus:
    iv = _TF_MAP.get(tf.upper())
    if iv is None:
        raise ValueError(f"Unsupported TF: {tf}")
    handler = TA_Handler(symbol=symbol, exchange=exchange, screener=screener, interval=iv)
    a = handler.get_analysis()
    return TVConsensus(
        tf=tf,
        recommendation=a.summary["RECOMMENDATION"],
        buy=int(a.summary["BUY"]),
        sell=int(a.summary["SELL"]),
        neutral=int(a.summary["NEUTRAL"]),
        oscillators_reco=a.oscillators["RECOMMENDATION"],
        moving_averages_reco=a.moving_averages["RECOMMENDATION"],
    )


def fetch_consensus(
    symbol: str = "XAUUSD",
    exchange: str = "OANDA",
    screener: str = "cfd",
    tfs: list[str] | None = None,
    force_refresh: bool = False,
) -> dict[str, TVConsensus]:
    """Lấy consensus cho nhiều khung. Cache 5 phút mỗi (symbol,exchange,tf).

    Returns {"M15": TVConsensus, "H1": TVConsensus, "H4": TVConsensus}.
    Lỗi 1 khung → bỏ qua khung đó, log warning, không raise."""
    tfs = tfs or ["M15", "H1", "H4"]
    out: dict[str, TVConsensus] = {}
    now = time.time()
    for tf in tfs:
        key = (symbol, exchange, screener, tf)
        if not force_refresh:
            cached = _cache.data.get(key)
            cached_ts = _cache.ts.get(key, 0)
            if cached and (now - cached_ts) < CACHE_TTL_S:
                out[tf] = cached
                continue
        try:
            c = _fetch_one(symbol, exchange, screener, tf)
            _cache.data[key] = c
            _cache.ts[key] = now
            out[tf] = c
        except Exception as e:  # noqa: BLE001
            log.warning("TV consensus fetch failed for %s %s %s: %s", symbol, exchange, tf, e)
    return out


def to_dict(consensus_map: dict[str, TVConsensus]) -> dict:
    """Chuyển ra dict để nhồi vào LLM prompt (JSON-friendly)."""
    return {
        tf: {
            "recommendation": c.recommendation,
            "buy": c.buy,
            "sell": c.sell,
            "neutral": c.neutral,
            "oscillators": c.oscillators_reco,
            "moving_averages": c.moving_averages_reco,
            "bias": c.bias,
        }
        for tf, c in consensus_map.items()
    }
