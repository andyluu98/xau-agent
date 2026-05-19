"""Smoke test G5 news blackout — keyword/time intersection logic.

Mock Tavily HTTP response để test thuần logic, không gọi API thật."""
from __future__ import annotations

from xau_agent.news import tavily


def _reset_cache(monkeypatch) -> None:
    """Mỗi test bắt đầu với cache rỗng."""
    monkeypatch.setattr(tavily, "_blackout_cache", tavily._Cache())


def test_blackout_detects_fomc_imminent(monkeypatch) -> None:
    _reset_cache(monkeypatch)
    fake = {
        "answer": "FOMC rate decision in 1 hour",
        "results": [{"title": "Fed FOMC release at 14:00 GMT scheduled for today"}],
    }
    monkeypatch.setattr(tavily, "_search", lambda *a, **kw: fake)
    blocked, reason = tavily.detect_blackout(force_refresh=True)
    assert blocked is True
    assert "FOMC" in reason


def test_blackout_detects_cpi_imminent(monkeypatch) -> None:
    _reset_cache(monkeypatch)
    fake = {
        "answer": "US CPI data release imminent",
        "results": [{"title": "Inflation report minutes away"}],
    }
    monkeypatch.setattr(tavily, "_search", lambda *a, **kw: fake)
    blocked, _ = tavily.detect_blackout(force_refresh=True)
    assert blocked is True


def test_blackout_ignores_today_without_strong_signal(monkeypatch) -> None:
    """'today' đơn lẻ không đủ — phải có 'in X hours' / 'imminent' / 'release at'."""
    _reset_cache(monkeypatch)
    fake = {
        "answer": "Gold price today influenced by Fed and FOMC",
        "results": [{"title": "XAU/USD analysis today"}],
    }
    monkeypatch.setattr(tavily, "_search", lambda *a, **kw: fake)
    blocked, _ = tavily.detect_blackout(force_refresh=True)
    assert blocked is False  # generic "today" mention shouldn't trigger


def test_blackout_skips_when_no_event(monkeypatch) -> None:
    _reset_cache(monkeypatch)
    fake = {
        "answer": "Gold trading sideways, no major news",
        "results": [{"title": "XAU/USD daily analysis"}],
    }
    monkeypatch.setattr(tavily, "_search", lambda *a, **kw: fake)
    blocked, _ = tavily.detect_blackout(force_refresh=True)
    assert blocked is False


def test_blackout_skips_when_event_no_time(monkeypatch) -> None:
    """Có keyword FOMC nhưng không có time indicator → không blackout."""
    _reset_cache(monkeypatch)
    fake = {
        "answer": "Historical analysis of FOMC decisions and their impact",
        "results": [{"title": "FOMC retrospective Q1 2024"}],
    }
    monkeypatch.setattr(tavily, "_search", lambda *a, **kw: fake)
    blocked, _ = tavily.detect_blackout(force_refresh=True)
    assert blocked is False


def test_blackout_failsafe_on_tavily_error(monkeypatch) -> None:
    """Tavily error → return False (không block bot do lỗi mạng)."""
    _reset_cache(monkeypatch)

    def boom(*a, **kw):
        raise tavily.TavilyError("network down")
    monkeypatch.setattr(tavily, "_search", boom)
    blocked, reason = tavily.detect_blackout(force_refresh=True)
    assert blocked is False
    assert "fail-safe" in reason
