"""Smoke test journal: write/read CSV + parse helpers."""
from __future__ import annotations

from xau_agent import journal


def test_parse_macro_bias_strength_valid() -> None:
    text = "...phân tích...\n\nBIAS=BEAR  STRENGTH=7/10"
    bias, strength = journal.parse_macro_bias_strength(text)
    assert bias == "BEAR"
    assert strength == "7/10"


def test_parse_macro_bias_strength_missing() -> None:
    bias, strength = journal.parse_macro_bias_strength("no marker here")
    assert bias == ""
    assert strength == ""


def test_summarize_truncates() -> None:
    long = "a" * 300
    out = journal.summarize(long, max_len=100)
    assert len(out) == 100
    assert out.endswith("...")


def test_summarize_handles_newlines() -> None:
    text = "line1\n\n   line2  \t line3"
    out = journal.summarize(text, max_len=50)
    assert "\n" not in out
    assert "line1 line2 line3" in out


def test_log_and_read_roundtrip(tmp_path, monkeypatch) -> None:
    """Redirect journal CSV path to tmp dir, log 1 trade, read back."""
    csv_path = tmp_path / "trades.csv"
    monkeypatch.setattr(journal, "STATE_DIR", tmp_path)
    monkeypatch.setattr(journal, "TRADES_CSV", csv_path)

    rec = journal.TradeRecord(
        ticket=12345, side="SELL", entry=4540.5, sl=4555.0, tp=4520.0,
        lot=0.02, atr=12.5, rsi=48.0, macd_hist=-2.1,
        trend_h1="DOWN", trend_h4="DOWN",
        tv_m15_reco="SELL", tv_h1_reco="STRONG_SELL", tv_h4_reco="SELL",
        macro_bias="BEAR", macro_strength="7/10",
        judge_decision="GO", judge_confidence=72,
        judge_summary="strong bearish setup",
        user_decision="YES", dry_run=False,
    )
    journal.log_trade(rec)
    journal.log_trade(rec)  # 2 dòng

    rows = journal.read_trades(limit=0)
    assert len(rows) == 2
    assert rows[0]["ticket"] == "12345"
    assert rows[0]["side"] == "SELL"
    assert rows[0]["judge_decision"] == "GO"
    assert rows[0]["macro_bias"] == "BEAR"
    assert rows[0]["dry_run"] == "False"


def test_read_trades_empty_when_no_file(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "trades.csv"
    monkeypatch.setattr(journal, "STATE_DIR", tmp_path)
    monkeypatch.setattr(journal, "TRADES_CSV", csv_path)
    assert journal.read_trades() == []
