"""Execution Trader agent (vai #7). Chỉ gọi khi Judge quyết GO.

Khác với Bull/Bear/Judge (quyết có/không), Execution Trader thiết kế CHI TIẾT entry:
- entry_strategy: vào ngay vs đợi pullback vs đợi breakout
- lot_multiplier: 0.5x/1x/1.5x so với default lot
- hold_rule: cách quản lý lệnh sau khi vào (TP, trailing, BE, close-before-news)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

from xau_agent.llm.deepseek import chat
from xau_agent.llm.prompts import SYSTEM_BASE, TRADER_ROLE

log = logging.getLogger(__name__)

EntryStrategy = Literal["now", "pullback_ema20", "breakout"]
HoldRule = Literal["to_tp", "close_before_news", "trail_after_1atr", "be_at_1atr"]


@dataclass(frozen=True)
class ExecutionPlan:
    entry_strategy: str          # 'now' | 'pullback_ema20' | 'breakout_X'
    entry_price_hint: float      # giá đề xuất vào (nếu pullback/breakout)
    lot_multiplier: float        # 0.5 / 1.0 / 1.5
    hold_rule: str               # 'to_tp' | 'close_before_news' | 'trail_after_1atr' | 'be_at_1atr'
    notes: str                   # 1-2 câu giải thích


def _format_context(setup: dict, trend: dict, news: str, tv: dict | None,
                    macro: str, verdict_summary: str) -> str:
    parts = [
        "## Setup (Python tính)",
        json.dumps(setup, ensure_ascii=False, indent=2),
        "",
        "## Trend H1+H4",
        json.dumps(trend, ensure_ascii=False, indent=2),
    ]
    if tv:
        parts += ["", "## TV consensus", json.dumps(tv, ensure_ascii=False, indent=2)]
    parts += [
        "", "## News brief", news or "(no news)",
        "", f"## Macro context\n{macro}",
        "", f"## Judge verdict\n{verdict_summary}",
    ]
    return "\n".join(parts)


def _parse_plan(raw: str, fallback_entry: float) -> ExecutionPlan:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        d = json.loads(cleaned)
        return ExecutionPlan(
            entry_strategy=str(d.get("entry_strategy", "now")),
            entry_price_hint=float(d.get("entry_price_hint", fallback_entry)),
            lot_multiplier=float(d.get("lot_multiplier", 1.0)),
            hold_rule=str(d.get("hold_rule", "to_tp")),
            notes=str(d.get("notes", "")),
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        log.warning("ExecutionPlan parse failed (%s); raw=%r", e, raw[:200])
        return ExecutionPlan(
            entry_strategy="now",
            entry_price_hint=fallback_entry,
            lot_multiplier=1.0,
            hold_rule="to_tp",
            notes=f"fallback (parse error): {raw[:120]}",
        )


def design_execution(setup: dict, trend: dict, news: str, tv: dict | None,
                     macro: str, verdict_summary: str) -> ExecutionPlan:
    """Gọi LLM thiết kế entry plan. Chỉ chạy sau Judge GO."""
    ctx = _format_context(setup, trend, news, tv, macro, verdict_summary)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + TRADER_ROLE},
        {"role": "user", "content": ctx + "\n\nThiết kế entry plan chi tiết. Trả JSON."},
    ]
    raw = chat(msgs, temperature=0.3, max_tokens=300, json_mode=True)
    fallback_entry = float(setup.get("entry", 0.0))
    return _parse_plan(raw, fallback_entry)
