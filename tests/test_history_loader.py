"""Test history.loader.build_brief — focus journal CSV path (MT5 unavailable in CI)."""
from __future__ import annotations

import csv
from dataclasses import fields
from pathlib import Path

import pytest

from xau_agent import journal as journal_mod
from xau_agent.history import build_brief


@pytest.fixture
def temp_journal(tmp_path: Path, monkeypatch):
    """Redirect journal CSV to a temp file with fixture rows."""
    csv_path = tmp_path / "trades.csv"
    monkeypatch.setattr(journal_mod, "TRADES_CSV", csv_path)
    monkeypatch.setattr(journal_mod, "STATE_DIR", tmp_path)

    rows = [
        {
            "timestamp": "2026-05-18T10:00:00",
            "ticket": 0, "side": "SELL", "entry": 4540.0, "sl": 4555.0, "tp": 4520.0,
            "lot": 0.01, "atr": 8.0, "rsi": 37.0, "macd_hist": -2.0,
            "trend_h1": "DOWN", "trend_h4": "DOWN",
            "tv_m15_reco": "SELL", "tv_h1_reco": "STRONG_SELL", "tv_h4_reco": "STRONG_SELL",
            "news_tldr": "", "bull_summary": "", "bear_summary": "",
            "macro_bias": "BEAR", "macro_strength": "8/10",
            "judge_decision": "GO", "judge_confidence": 75, "judge_summary": "go",
            "exec_strategy": "now", "exec_lot_mul": 1.0, "exec_hold_rule": "to_tp",
            "user_decision": "YES", "exit_time": "", "exit_price": 0.0,
            "pnl_usc": 0.0, "hold_minutes": 0, "dry_run": True,
        },
        {
            "timestamp": "2026-05-19T04:46:00",
            "ticket": 0, "side": "SELL", "entry": 4541.0, "sl": 4554.0, "tp": 4520.0,
            "lot": 0.01, "atr": 8.0, "rsi": 38.0, "macd_hist": -2.2,
            "trend_h1": "DOWN", "trend_h4": "DOWN",
            "tv_m15_reco": "SELL", "tv_h1_reco": "STRONG_SELL", "tv_h4_reco": "STRONG_SELL",
            "news_tldr": "", "bull_summary": "", "bear_summary": "",
            "macro_bias": "BEAR", "macro_strength": "8/10",
            "judge_decision": "SKIP", "judge_confidence": 65, "judge_summary": "skip",
            "exec_strategy": "", "exec_lot_mul": 1.0, "exec_hold_rule": "",
            "user_decision": "", "exit_time": "", "exit_price": 0.0,
            "pnl_usc": 0.0, "hold_minutes": 0, "dry_run": True,
        },
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        names = [fld.name for fld in fields(journal_mod.TradeRecord)]
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return csv_path


def test_build_brief_returns_journal_when_mt5_unavailable(temp_journal):
    """MT5 not connected → still produces brief from journal CSV."""
    brief = build_brief(days=7, journal_limit=10)
    assert brief is not None
    # MT5 not available in CI → closed_deals=0, but journal text should appear
    assert "Journal CSV" in brief.text
    assert "GO(75)" in brief.text or "judge=GO" in brief.text
    assert "SKIP(65)" in brief.text or "judge=SKIP" in brief.text


def test_build_brief_empty_when_no_data(tmp_path: Path, monkeypatch):
    """No journal file, no MT5 → graceful brief."""
    monkeypatch.setattr(journal_mod, "TRADES_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(journal_mod, "STATE_DIR", tmp_path)
    brief = build_brief(days=7, journal_limit=5)
    assert brief.closed_deals == 0
    assert brief.open_positions == 0
    assert brief.pending_orders == 0
    assert brief.has_data is False


def test_journal_limit_respected(temp_journal):
    """journal_limit=1 → chỉ 1 entry trong text."""
    brief = build_brief(days=7, journal_limit=1)
    assert "Journal CSV" in brief.text
    # 1 entry only → exactly 1 line bắt đầu với "  " (indent)
    journal_lines = [line for line in brief.text.split("\n") if line.startswith("  ") and "judge=" in line]
    assert len(journal_lines) == 1
