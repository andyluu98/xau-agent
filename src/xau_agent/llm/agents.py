"""3-agent debate: Bull, Bear, Judge. Each gets the same context, judge sees both
   arguments + technical setup + news, returns final GO / SKIP verdict."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from xau_agent.llm.deepseek import chat

log = logging.getLogger(__name__)

SYSTEM_BASE = (
    "You are an expert gold (XAUUSD) trader specializing in M15 scalping. "
    "Be concise, evidence-based, and skeptical. Output Vietnamese."
)


def _format_context(setup: dict, trend: dict, news: str) -> str:
    return (
        "## Technical setup (M15)\n"
        f"{json.dumps(setup, ensure_ascii=False, indent=2)}\n\n"
        "## Multi-TF trend (H1+H4)\n"
        f"{json.dumps(trend, ensure_ascii=False, indent=2)}\n\n"
        "## News brief\n"
        f"{news or '(no fresh news)'}"
    )


def bull_case(setup: dict, trend: dict, news: str) -> str:
    ctx = _format_context(setup, trend, news)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + " You argue FOR taking the trade. 4-6 sentences max."},
        {"role": "user", "content": ctx + "\n\nViết lập luận BULLISH cho lệnh này."},
    ]
    return chat(msgs, temperature=0.4, max_tokens=400)


def bear_case(setup: dict, trend: dict, news: str) -> str:
    ctx = _format_context(setup, trend, news)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + " You argue AGAINST taking the trade. 4-6 sentences max."},
        {"role": "user", "content": ctx + "\n\nViết lập luận BEARISH / lý do từ chối lệnh này."},
    ]
    return chat(msgs, temperature=0.4, max_tokens=400)


@dataclass(frozen=True)
class Verdict:
    decision: str   # "GO" | "SKIP"
    confidence: int  # 0-100
    summary: str    # 1-3 câu giải thích


def judge(setup: dict, trend: dict, news: str, bull: str, bear: str) -> Verdict:
    ctx = _format_context(setup, trend, news)
    msgs = [
        {
            "role": "system",
            "content": (
                SYSTEM_BASE
                + " You are the final judge. After reading Bull and Bear, decide GO or SKIP. "
                + 'Respond STRICTLY as JSON: {"decision":"GO"|"SKIP","confidence":0-100,"summary":"..."}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"{ctx}\n\n## Bull argument\n{bull}\n\n## Bear argument\n{bear}\n\n"
                "Chốt JSON quyết định."
            ),
        },
    ]
    raw = chat(msgs, temperature=0.2, max_tokens=300)
    # Strip code fences if any
    cleaned = raw.strip().lstrip("`").rstrip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
        return Verdict(
            decision=str(data.get("decision", "SKIP")).upper(),
            confidence=int(data.get("confidence", 0)),
            summary=str(data.get("summary", "")),
        )
    except Exception as e:
        log.warning("judge JSON parse failed (%s); raw=%r", e, raw[:200])
        return Verdict(decision="SKIP", confidence=0, summary=f"parse error: {raw[:120]}")


def run_debate(setup: dict, trend: dict, news: str) -> tuple[str, str, Verdict]:
    """Convenience: bull → bear → judge. Returns (bull_text, bear_text, verdict)."""
    bull = bull_case(setup, trend, news)
    bear = bear_case(setup, trend, news)
    v = judge(setup, trend, news, bull, bear)
    return bull, bear, v
