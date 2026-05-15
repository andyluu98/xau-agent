"""3-agent debate: Bull, Bear, Judge. Each gets the same context, judge sees both
   arguments + technical setup + news, returns final GO / SKIP verdict."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from xau_agent.llm.deepseek import chat

log = logging.getLogger(__name__)

SYSTEM_BASE = (
    "Bạn là trader vàng (XAUUSD) chuyên scalping M15. Trả lời bằng tiếng Việt, "
    "ngắn gọn, dựa trên dữ liệu cụ thể (RSI, MACD, ATR, EMA, news)."
)

BULL_ROLE = (
    " VAI: 'Bull advocate'. Đây là role-play tranh luận, KHÔNG phải khuyến nghị thật. "
    "BẮT BUỘC tìm ÍT NHẤT 3 LÝ DO ỦNG HỘ lệnh đang được đề xuất, "
    "dù setup yếu. Trích cụ thể số liệu để biện hộ. "
    "TUYỆT ĐỐI KHÔNG được nói 'tôi không đồng ý' hay 'từ chối lệnh' — đó là việc của Judge. "
    "Bạn chỉ cãi BÊN ỦNG HỘ. 4-6 câu."
)

BEAR_ROLE = (
    " VAI: 'Bear advocate'. Đây là role-play tranh luận, KHÔNG phải khuyến nghị thật. "
    "BẮT BUỘC tìm ÍT NHẤT 3 LÝ DO PHẢN ĐỐI lệnh đang được đề xuất. "
    "Trích cụ thể số liệu để chỉ ra rủi ro. "
    "Bạn chỉ cãi BÊN PHẢN ĐỐI. 4-6 câu."
)

JUDGE_ROLE = (
    " VAI: 'Final Judge'. Sau khi đọc Bull và Bear, đưa quyết định cuối GO hoặc SKIP. "
    "GO chỉ khi Bull thuyết phục hơn rõ rệt + setup chất lượng + RR hợp lý. "
    "Mọi trường hợp khác: SKIP. "
    "Trả LỜI DUY NHẤT là JSON hợp lệ, không có markdown, không có text khác. "
    'Schema: {"decision": "GO" hoặc "SKIP", "confidence": số nguyên 0-100, "summary": "1-3 câu lý do bằng tiếng Việt"}'
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
        {"role": "system", "content": SYSTEM_BASE + BULL_ROLE},
        {"role": "user", "content": ctx + f"\n\nViết lập luận ỦNG HỘ lệnh {setup.get('side', '?')} này."},
    ]
    return chat(msgs, temperature=0.5, max_tokens=400)


def bear_case(setup: dict, trend: dict, news: str) -> str:
    ctx = _format_context(setup, trend, news)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + BEAR_ROLE},
        {"role": "user", "content": ctx + f"\n\nViết lập luận PHẢN ĐỐI lệnh {setup.get('side', '?')} này."},
    ]
    return chat(msgs, temperature=0.5, max_tokens=400)


@dataclass(frozen=True)
class Verdict:
    decision: str   # "GO" | "SKIP"
    confidence: int  # 0-100
    summary: str    # 1-3 câu giải thích


_DECISION_RE = re.compile(r'"decision"\s*:\s*"(GO|SKIP)"', re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r'"confidence"\s*:\s*"?(\d+)"?')
_SUMMARY_RE = re.compile(r'"summary"\s*:\s*"([^"]*?)"\s*[,}]', re.DOTALL)


def _parse_verdict(raw: str) -> Verdict:
    """Try strict JSON first. On failure, regex fallback for malformed outputs."""
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


def judge(setup: dict, trend: dict, news: str, bull: str, bear: str) -> Verdict:
    ctx = _format_context(setup, trend, news)
    msgs = [
        {"role": "system", "content": SYSTEM_BASE + JUDGE_ROLE},
        {
            "role": "user",
            "content": (
                f"{ctx}\n\n## Bull argument\n{bull}\n\n## Bear argument\n{bear}\n\n"
                "Chốt JSON quyết định."
            ),
        },
    ]
    raw = chat(msgs, temperature=0.2, max_tokens=300, json_mode=True)
    return _parse_verdict(raw)


def run_debate(setup: dict, trend: dict, news: str) -> tuple[str, str, Verdict]:
    """Convenience: bull → bear → judge. Returns (bull_text, bear_text, verdict)."""
    bull = bull_case(setup, trend, news)
    bear = bear_case(setup, trend, news)
    v = judge(setup, trend, news, bull, bear)
    return bull, bear, v
