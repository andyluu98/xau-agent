"""Config smoke: defaults load + trend_tf_list parses."""
from __future__ import annotations

from xau_agent.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.symbol == "XAUUSD"
    assert s.entry_tf == "M15"
    assert s.trend_tf_list == ["H1", "H4"]
    assert s.dry_run is True
    assert s.rr_ratio > 1.0


def test_trend_tfs_override() -> None:
    s = Settings(_env_file=None, trend_tfs="h1, h4 , d1")
    assert s.trend_tf_list == ["H1", "H4", "D1"]
