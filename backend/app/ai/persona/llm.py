"""Sync vLLM client for the persona pipeline (ported from prototype/boyfriend/llm.py).

Every call here blocks, so callers must run it in a worker thread (asyncio.to_thread).
"""

from collections.abc import Iterator
from functools import lru_cache

from openai import OpenAI

from app.config import get_settings

ANALYSIS_TIMEOUT_SEC = 600  # style/memory extraction over ~1000 messages


@lru_cache
def _client(timeout: float) -> OpenAI:
    settings = get_settings()
    base_url = settings.llm_base_url.rstrip("/") + "/v1"
    # vLLM runs without --api-key behind the SSH tunnel; the client still needs a value.
    return OpenAI(base_url=base_url, api_key="EMPTY", timeout=timeout)


def _extra(thinking: bool) -> dict:
    # Qwen3 defaults to thinking mode; keep it off for chat so replies stay fast.
    return {"chat_template_kwargs": {"enable_thinking": thinking}}


def chat(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    thinking: bool = False,
    json_mode: bool = False,
    long: bool = False,
) -> str:
    settings = get_settings()
    timeout = ANALYSIS_TIMEOUT_SEC if long else settings.llm_timeout_sec
    kw = {"response_format": {"type": "json_object"}} if json_mode else {}
    r = _client(timeout).chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature,
        top_p=0.9,
        max_tokens=max_tokens,
        extra_body=_extra(thinking),
        **kw,
    )
    return (r.choices[0].message.content or "").strip()


def stream(
    messages: list[dict], *, temperature: float = 0.85, max_tokens: int = 300
) -> Iterator[str]:
    settings = get_settings()
    s = _client(settings.llm_timeout_sec).chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature,
        top_p=0.9,
        max_tokens=max_tokens,
        stream=True,
        presence_penalty=0.3,
        extra_body=_extra(False),
    )
    for chunk in s:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
