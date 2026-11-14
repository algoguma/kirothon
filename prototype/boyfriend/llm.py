"""원격 vLLM 위의 Qwen3.8 호출 래퍼 (OpenAI 호환 API)."""
from __future__ import annotations

from typing import Iterator

from openai import OpenAI

from . import config, tunnel

_client = OpenAI(base_url=config.VLLM_BASE_URL, api_key=config.VLLM_API_KEY, timeout=600)


def _extra(thinking: bool) -> dict:
    # Qwen3.8은 기본이 thinking 모드 → 채팅에서는 꺼서 빠르고 자연스럽게
    return {"chat_template_kwargs": {"enable_thinking": thinking}}


def chat(messages: list[dict], *, temperature=0.7, max_tokens=1024,
         thinking=False, json_mode=False) -> str:
    kw = {"response_format": {"type": "json_object"}} if json_mode else {}
    r = _client.chat.completions.create(
        model=config.VLLM_MODEL, messages=messages, temperature=temperature,
        top_p=0.9, max_tokens=max_tokens, extra_body=_extra(thinking), **kw)
    return (r.choices[0].message.content or "").strip()


def stream(messages: list[dict], *, temperature=0.85, max_tokens=300) -> Iterator[str]:
    s = _client.chat.completions.create(
        model=config.VLLM_MODEL, messages=messages, temperature=temperature,
        top_p=0.9, max_tokens=max_tokens, stream=True,
        presence_penalty=0.3, extra_body=_extra(False))
    for chunk in s:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def health() -> str:
    """vLLM 연결 확인 (필요하면 .env의 SSH_TUNNEL로 터널을 먼저 자동 연결)"""
    tunnel.ensure()
    return ", ".join(m.id for m in _client.models.list().data)
