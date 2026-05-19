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


# === G5 — News blackout detector ====================================
# Mục tiêu: nếu sắp có tin lớn (FOMC/CPI/NFP/Fed speech) trong ~1 giờ tới,
# bot tự skip phiên để tránh dính SL do volatile spike.

HIGH_IMPACT_KEYWORDS = (
    "FOMC", "CPI", "NFP", "PCE", "Fed rate decision",
    "rate decision", "Fed Chair", "Powell", "non-farm",
    "non farm payroll", "core inflation",
)
# Từ chỉ "sắp xảy ra" — STRICT, không nhận "today" trần (quá rộng → false positive)
IMMINENCE_PATTERNS = (
    "in 1 hour", "in 2 hours", "in 30 minutes", "in 60 minutes",
    "in 90 minutes", "in an hour", "imminent", "minutes away",
    "next hour", "this hour", "due in",
    "release at", "scheduled for today",
    "hours away", "later today at",
)
BLACKOUT_QUERY = (
    "FOMC OR CPI OR NFP OR Fed rate decision today imminent "
    "next hours release schedule"
)
BLACKOUT_CACHE_TTL_S = 1800  # 30 phút

# Negation patterns — Tavily hay trả "No Fed rate decision is imminent today"
# Nếu thấy negation gần keyword/time signal → KHÔNG block.
NEGATION_PATTERNS = (
    "no fed", "no fomc", "no cpi", "no nfp", "no rate decision",
    "not imminent", "not scheduled", "not today",
    "no major", "no high-impact", "no upcoming",
    "isn't", "isn't scheduled", "won't", "no release today",
    "no fed rate", "no major economic",
)

_blackout_cache = _Cache()


def detect_blackout(force_refresh: bool = False) -> tuple[bool, str]:
    """Kiểm có tin lớn sắp xảy ra trong ~1h tới không.

    Logic: query Tavily với từ khóa imminent + high-impact, check intersection.
    Returns (is_blackout, reason). Cache 30 phút.

    Fail-safe: lỗi Tavily → return (False, ...) — KHÔNG block bot vì lỗi mạng.
    """
    now = time.time()
    if not force_refresh and _blackout_cache.text and (now - _blackout_cache.fetched_at) < BLACKOUT_CACHE_TTL_S:
        cached = _blackout_cache.text
        is_blk = cached.startswith("BLACKOUT|")
        return is_blk, cached.split("|", 1)[1] if "|" in cached else cached

    try:
        data = _search(BLACKOUT_QUERY, max_results=5)
    except TavilyError as e:
        log.warning("blackout check Tavily failed: %s", e)
        return False, f"tavily error, fail-safe no blackout: {e}"

    answer = (data.get("answer") or "").lower()
    titles = " | ".join((r.get("title") or "").lower() for r in data.get("results", []))
    haystack = f"{answer} {titles}"

    # Check negation FIRST — nếu Tavily nói rõ "no FOMC today" → KHÔNG block
    matched_negation = next((n for n in NEGATION_PATTERNS if n in haystack), None)
    if matched_negation:
        _blackout_cache.text = f"CLEAR|Tavily xác nhận không có tin lớn (negation: '{matched_negation}')"
        _blackout_cache.fetched_at = now
        return False, f"Tavily xác nhận không có tin (signal '{matched_negation}')"

    matched_event = next((kw for kw in HIGH_IMPACT_KEYWORDS if kw.lower() in haystack), None)
    matched_time = next((w for w in IMMINENCE_PATTERNS if w in haystack), None)

    if matched_event and matched_time:
        reason = f"sắp có tin '{matched_event}' (signal '{matched_time}')"
        _blackout_cache.text = f"BLACKOUT|{reason}"
        _blackout_cache.fetched_at = now
        return True, reason

    _blackout_cache.text = "CLEAR|không có tin lớn sắp diễn ra"
    _blackout_cache.fetched_at = now
    return False, "không có tin lớn sắp diễn ra"
