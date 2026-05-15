"""DeepSeek API client. Uses OpenAI-compatible /chat/completions endpoint."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from xau_agent.config import get_settings

log = logging.getLogger(__name__)


class DeepSeekError(RuntimeError):
    pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 800,
    model: str | None = None,
) -> str:
    """Send chat messages, return assistant content string."""
    s = get_settings()
    if not s.deepseek_api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY missing in .env")

    payload: dict[str, Any] = {
        "model": model or s.deepseek_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    url = f"{s.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {s.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload, headers=headers)
    if r.status_code >= 400:
        raise DeepSeekError(f"DeepSeek HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise DeepSeekError(f"Malformed response: {data}") from e
