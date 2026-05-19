"""Test xau_agent.llm.dayplan._parse_dayplan — JSON robustness."""
from __future__ import annotations

from xau_agent.llm.dayplan import _parse_dayplan


def test_parse_valid_json():
    raw = """{
      "day_bias": "BEAR",
      "bias_strength": 8,
      "key_levels": [
        {"price": 4555.0, "note": "kháng cự EMA50 H1"},
        {"price": 4530.0, "note": "hỗ trợ swing low ngày"}
      ],
      "scenarios": [
        {"trigger": "phá 4555", "action": "đảo BUY breakout", "risk": "fakeout"},
        {"trigger": "phá 4530", "action": "thêm SELL", "risk": "stop hunt"}
      ],
      "news_risks": "CPI 13:30 UTC",
      "daily_risk_note": "Max 2 lệnh, mỗi lệnh 1% balance"
    }"""
    plan = _parse_dayplan(raw, macro="bias=BEAR test")
    assert plan.day_bias == "BEAR"
    assert plan.bias_strength == 8
    assert len(plan.key_levels) == 2
    assert plan.key_levels[0].price == 4555.0
    assert "kháng cự" in plan.key_levels[0].note
    assert len(plan.scenarios) == 2
    assert plan.scenarios[0].trigger == "phá 4555"
    assert "CPI" in plan.news_risks
    assert "Max 2" in plan.daily_risk_note
    assert plan.macro_text == "bias=BEAR test"


def test_parse_handles_code_fence():
    """LLM hay wrap output trong ```json ... ``` — parser phải strip."""
    raw = '```json\n{"day_bias":"BULL","bias_strength":6,"key_levels":[],"scenarios":[],"news_risks":"","daily_risk_note":""}\n```'
    plan = _parse_dayplan(raw, macro="")
    assert plan.day_bias == "BULL"
    assert plan.bias_strength == 6


def test_parse_string_levels_fallback():
    """Một số LLM trả key_levels là list of string thay vì list of dict."""
    raw = '{"day_bias":"BEAR","bias_strength":7,"key_levels":["4555 — EMA50 H1","4530 — đáy ngày"],"scenarios":[],"news_risks":"","daily_risk_note":""}'
    plan = _parse_dayplan(raw, macro="")
    assert len(plan.key_levels) == 2
    assert plan.key_levels[0].price == 4555.0
    assert "EMA50" in plan.key_levels[0].note


def test_parse_malformed_returns_safe_fallback():
    raw = "garbage not-json here"
    plan = _parse_dayplan(raw, macro="m")
    assert plan.day_bias == "RANGE"
    assert plan.bias_strength == 0
    assert "parse error" in plan.news_risks
    assert plan.macro_text == "m"


def test_parse_missing_optional_fields():
    """JSON valid nhưng thiếu fields → default values."""
    raw = '{"day_bias":"RANGE","bias_strength":5}'
    plan = _parse_dayplan(raw, macro="")
    assert plan.day_bias == "RANGE"
    assert plan.key_levels == []
    assert plan.scenarios == []
    assert plan.news_risks == ""
