"""6-vai debate orchestration:
  1. Macro Analyst → 2. Bull → 3. Bear → 4. Risk Aggressive
  5. Risk Neutral → 6. Risk Conservative → Judge → (Execution Trader nếu GO)

Tổng: 7 LLM calls / phiên (8 nếu Judge GO + Trader).
Output: DebateResult với mọi text + Verdict cuối."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from xau_agent.llm.deepseek import chat
from xau_agent.llm.prompts import (
    BEAR_ROLE, BULL_ROLE, JUDGE_ROLE, MACRO_ROLE, RISK_AGGRESSIVE_ROLE,
    RISK_CONSERVATIVE_ROLE, RISK_NEUTRAL_ROLE, SYSTEM_BASE,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Verdict:
    decision: str    # "GO" | "SKIP"
    confidence: int  # 0-100
    summary: str


@dataclass(frozen=True)
class DebateResult:
    macro: str
    bull: str
    bear: str
    risk_aggressive: str
    risk_neutral: str
    risk_conservative: str
    verdict: Verdict


def _format_context(setup: dict, trend: dict, news: str, tv: dict | None = None) -> str:
    parts = [
        "## Technical setup (M15)", json.dumps(setup, ensure_ascii=False, indent=2),
        "",
        "## Multi-TF trend (H1+H4) — EMA50/200 based",
        json.dumps(trend, ensure_ascii=False, indent=2),
    ]
    if tv:
        parts += ["", "## TradingView 26-indicator consensus", json.dumps(tv, ensure_ascii=False, indent=2)]
    parts += ["", "## News brief", news or "(no fresh news)"]
    return "\n".join(parts)


def _call_role(role_prompt: str, ctx: str, user_directive: str, temp: float = 0.5, max_tok: int = 400) -> str:
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + role_prompt},
        {"role": "user", "content": ctx + "\n\n" + user_directive},
    ]
    return chat(msgs, temperature=temp, max_tokens=max_tok)


def macro_analyst(setup: dict, trend: dict, news: str, tv: dict | None = None) -> str:
    ctx = _format_context(setup, trend, news, tv)
    return _call_role(MACRO_ROLE, ctx,
                      f"Phân tích context tổng quan cho lệnh {setup.get('side', '?')} này.",
                      temp=0.3, max_tok=350)


def bull_case(setup: dict, trend: dict, news: str, tv: dict | None = None, macro: str = "") -> str:
    ctx = _format_context(setup, trend, news, tv)
    if macro:
        ctx += f"\n\n## Macro Analyst context\n{macro}"
    return _call_role(BULL_ROLE, ctx, f"Viết lập luận ỦNG HỘ lệnh {setup.get('side', '?')} này.", temp=0.5)


def bear_case(setup: dict, trend: dict, news: str, tv: dict | None = None, macro: str = "") -> str:
    ctx = _format_context(setup, trend, news, tv)
    if macro:
        ctx += f"\n\n## Macro Analyst context\n{macro}"
    return _call_role(BEAR_ROLE, ctx, f"Viết lập luận PHẢN ĐỐI lệnh {setup.get('side', '?')} này.", temp=0.5)


def _risk_call(role: str, setup: dict, trend: dict, news: str, tv: dict | None, bull: str, bear: str) -> str:
    ctx = (_format_context(setup, trend, news, tv)
           + f"\n\n## Bull argument\n{bull}\n\n## Bear argument\n{bear}")
    return _call_role(role, ctx, "Đưa quan điểm rủi ro của bạn cho lệnh này.", temp=0.4, max_tok=300)


def risk_aggressive(setup, trend, news, tv, bull, bear) -> str:
    return _risk_call(RISK_AGGRESSIVE_ROLE, setup, trend, news, tv, bull, bear)


def risk_neutral(setup, trend, news, tv, bull, bear) -> str:
    return _risk_call(RISK_NEUTRAL_ROLE, setup, trend, news, tv, bull, bear)


def risk_conservative(setup, trend, news, tv, bull, bear) -> str:
    return _risk_call(RISK_CONSERVATIVE_ROLE, setup, trend, news, tv, bull, bear)


_DECISION_RE = re.compile(r'"decision"\s*:\s*"(GO|SKIP)"', re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r'"confidence"\s*:\s*"?(\d+)"?')
_SUMMARY_RE = re.compile(r'"summary"\s*:\s*"([^"]*?)"\s*[,}]', re.DOTALL)


def _parse_verdict(raw: str) -> Verdict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
        return Verdict(
            decision=str(data.get("decision", "SKIP")).upper(),
            confidence=int(data.get("confidence", 0)),
            summary=str(data.get("summary", "")),
        )
    except (json.JSONDecodeError, ValueError):
        pass
    d = _DECISION_RE.search(cleaned)
    c = _CONFIDENCE_RE.search(cleaned)
    sm = _SUMMARY_RE.search(cleaned)
    if d:
        return Verdict(
            decision=d.group(1).upper(),
            confidence=int(c.group(1)) if c else 0,
            summary=(sm.group(1) if sm else cleaned[:200]).strip(),
        )
    log.warning("verdict parse failed; raw=%r", raw[:200])
    return Verdict(decision="SKIP", confidence=0, summary=f"parse error: {raw[:120]}")


def judge(setup: dict, trend: dict, news: str, tv: dict | None,
          macro: str, bull: str, bear: str,
          risk_agg: str, risk_neu: str, risk_con: str) -> Verdict:
    ctx = _format_context(setup, trend, news, tv)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + JUDGE_ROLE},
        {"role": "user", "content": (
            f"{ctx}\n\n"
            f"## Macro Analyst\n{macro}\n\n"
            f"## Bull argument\n{bull}\n\n"
            f"## Bear argument\n{bear}\n\n"
            f"## Risk Aggressive\n{risk_agg}\n\n"
            f"## Risk Neutral\n{risk_neu}\n\n"
            f"## Risk Conservative\n{risk_con}\n\n"
            "Chốt JSON quyết định cuối cùng."
        )},
    ]
    raw = chat(msgs, temperature=0.2, max_tokens=300, json_mode=True)
    return _parse_verdict(raw)


def run_debate(setup: dict, trend: dict, news: str, tv: dict | None = None) -> DebateResult:
    """Full 6-vai debate. Gọi tuần tự (không parallel vì Bull/Bear cần macro context)."""
    macro = macro_analyst(setup, trend, news, tv)
    bull = bull_case(setup, trend, news, tv, macro)
    bear = bear_case(setup, trend, news, tv, macro)
    risk_agg = risk_aggressive(setup, trend, news, tv, bull, bear)
    risk_neu = risk_neutral(setup, trend, news, tv, bull, bear)
    risk_con = risk_conservative(setup, trend, news, tv, bull, bear)
    v = judge(setup, trend, news, tv, macro, bull, bear, risk_agg, risk_neu, risk_con)
    return DebateResult(
        macro=macro, bull=bull, bear=bear,
        risk_aggressive=risk_agg, risk_neutral=risk_neu, risk_conservative=risk_con,
        verdict=v,
    )
