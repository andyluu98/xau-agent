"""Tavily search → short news brief for gold/USD/Fed. In-process 1h cache."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from xau_agent.config import get_settings

log = logging.getLogger(__name__)

DEFAULT_QUERY = (
    "XAUUSD gold price today AND (Fed OR CPI OR NFP OR DXY OR yields OR FOMC) latest news"
)
CACHE_TTL_S = 3600  # 1 hour


@dataclass
class _Cache:
    text: str = ""
    fetched_at: float = 0.0


_cache = _Cache()


class TavilyError(RuntimeError):
    pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def _search(query: str, max_results: int = 5) -> dict:
    s = get_settings()
    if not s.tavily_api_key:
        raise TavilyError("TAVILY_API_KEY missing in .env")
    payload = {
        "api_key": s.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post("https://api.tavily.com/search", json=payload)
    if r.status_code >= 400:
        raise TavilyError(f"Tavily HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def brief(query: Optional[str] = None, force_refresh: bool = False) -> str:
    """Return short markdown brief: 1 answer line + 5 bullet titles. Cached 1h."""
    now = time.time()
    if not force_refresh and _cache.text and (now - _cache.fetched_at) < CACHE_TTL_S:
        return _cache.text

    q = query or DEFAULT_QUERY
    try:
        data = _search(q, max_results=5)
    except TavilyError as e:
        log.warning("Tavily fetch failed: %s", e)
        return _cache.text or f"(news unavailable: {e})"

    answer = data.get("answer", "").strip()
    results = data.get("results", []) or []
    lines = []
    if answer:
        lines.append(f"**TL;DR:** {answer}")
    for r in results:
        title = (r.get("title") or "").strip()
        url = r.get("url", "")
        if title:
            lines.append(f"- {title} ({url})")
    text = "\n".join(lines) if lines else "(empty)"

    _cache.text = text
    _cache.fetched_at = now
    return text
