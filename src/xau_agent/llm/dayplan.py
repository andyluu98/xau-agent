"""Day Planner orchestration — 2 LLM calls (Macro + Day Planner).

Khác `run_debate`: không cãi nhau, không quyết GO/SKIP một lệnh, chỉ vẽ
kịch bản đa nhánh cho cả ngày. Cost ~$0.002/lần."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from xau_agent.llm.agents import macro_analyst
from xau_agent.llm.deepseek import chat
from xau_agent.llm.prompts import DAY_PLANNER_ROLE, SYSTEM_BASE

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeyLevel:
    price: float
    note: str


@dataclass(frozen=True)
class Scenario:
    trigger: str
    action: str
    risk: str


@dataclass(frozen=True)
class DayPlan:
    day_bias: str        # BULL | BEAR | RANGE
    bias_strength: int   # 1-10
    key_levels: list[KeyLevel] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    news_risks: str = ""
    daily_risk_note: str = ""
    macro_text: str = ""  # raw Macro Analyst output (for display)
    raw_json: str = ""    # raw planner JSON (for debug)


def _parse_dayplan(raw: str, macro: str) -> DayPlan:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("dayplan parse failed; raw=%r", raw[:300])
        return DayPlan(
            day_bias="RANGE", bias_strength=0,
            news_risks="(parse error)",
            daily_risk_note=raw[:200],
            macro_text=macro, raw_json=raw,
        )

    levels = []
    for lvl in data.get("key_levels", []):
        if isinstance(lvl, dict):
            try:
                levels.append(KeyLevel(price=float(lvl.get("price", 0)), note=str(lvl.get("note", ""))))
            except (TypeError, ValueError):
                continue
        elif isinstance(lvl, str):
            # vd "4555 — kháng cự EMA50 H1"
            m = re.match(r"\s*([\d.]+)\s*[-—:]?\s*(.*)", lvl)
            if m:
                try:
                    levels.append(KeyLevel(price=float(m.group(1)), note=m.group(2).strip()))
                except ValueError:
                    continue

    scenarios = []
    for sc in data.get("scenarios", []):
        if isinstance(sc, dict):
            scenarios.append(Scenario(
                trigger=str(sc.get("trigger", "")),
                action=str(sc.get("action", "")),
                risk=str(sc.get("risk", "")),
            ))

    return DayPlan(
        day_bias=str(data.get("day_bias", "RANGE")).upper(),
        bias_strength=int(data.get("bias_strength", 0) or 0),
        key_levels=levels,
        scenarios=scenarios,
        news_risks=str(data.get("news_risks", "")),
        daily_risk_note=str(data.get("daily_risk_note", "")),
        macro_text=macro,
        raw_json=raw,
    )


def run_dayplan(
    setup: dict, trend: dict, news: str, tv: dict | None,
    zones_summary: str, history_brief: str,
) -> DayPlan:
    """2 LLM calls: Macro Analyst (cho bias) → Day Planner (cho kịch bản).

    setup: setup giả định (chỉ để Macro có gốc tham chiếu, không trade)
    zones_summary: text tóm tắt zones (S/R, EMA, swing) — code-generated
    history_brief: text từ history.build_brief()
    """
    macro = macro_analyst(setup, trend, news, tv)

    ctx_parts = [
        "## Technical setup tham chiếu (KHÔNG phải lệnh để vào, chỉ để có gốc giá)",
        json.dumps(setup, ensure_ascii=False, indent=2),
        "",
        "## Multi-TF trend (H1+H4)",
        json.dumps(trend, ensure_ascii=False, indent=2),
    ]
    if tv:
        ctx_parts += ["", "## TradingView 26-indicator consensus", json.dumps(tv, ensure_ascii=False, indent=2)]
    ctx_parts += ["", "## Key zones (S/R + EMA + swing)", zones_summary or "(no zones)"]
    ctx_parts += ["", "## News brief", news or "(no news)"]
    ctx_parts += ["", "## History brief (account + journal)", history_brief or "(no history)"]
    ctx_parts += ["", f"## Macro Analyst đã luận:\n{macro}"]

    ctx = "\n".join(ctx_parts)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + DAY_PLANNER_ROLE},
        {"role": "user", "content": ctx + "\n\nVẽ KẾ HOẠCH NGÀY (JSON theo schema)."},
    ]
    raw = chat(msgs, temperature=0.3, max_tokens=900, json_mode=True)
    return _parse_dayplan(raw, macro)
