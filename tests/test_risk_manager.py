"""Smoke test risk_manager: flag file lifecycle + auto-reset logic."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from xau_agent import risk_manager as rm


def test_flag_lifecycle(tmp_path, monkeypatch) -> None:
    flag = tmp_path / "kill.flag"
    monkeypatch.setattr(rm, "STATE_DIR", tmp_path)
    monkeypatch.setattr(rm, "KILL_FLAG", flag)

    assert rm.is_killed() == (False, "")
    rm.arm_kill("test reason")
    killed, reason = rm.is_killed()
    assert killed is True
    assert "test reason" in reason
    assert rm.reset_kill() is True
    assert rm.is_killed() == (False, "")
    assert rm.reset_kill() is False  # nothing to reset second time


def test_flag_auto_reset_old_day(tmp_path, monkeypatch) -> None:
    """Flag từ ngày hôm qua → tự reset, không block."""
    flag = tmp_path / "kill.flag"
    monkeypatch.setattr(rm, "STATE_DIR", tmp_path)
    monkeypatch.setattr(rm, "KILL_FLAG", flag)

    yesterday = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    flag.write_text(f"{yesterday}|old reason", encoding="utf-8")
    killed, _ = rm.is_killed()
    assert killed is False
    # File should be removed by is_killed()
    assert not flag.exists()


def test_flag_today_still_active(tmp_path, monkeypatch) -> None:
    """Flag từ hôm nay → vẫn active."""
    flag = tmp_path / "kill.flag"
    monkeypatch.setattr(rm, "STATE_DIR", tmp_path)
    monkeypatch.setattr(rm, "KILL_FLAG", flag)

    rm.arm_kill("today reason")
    killed, _ = rm.is_killed()
    assert killed is True
