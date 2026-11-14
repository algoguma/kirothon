"""Backend <-> AI contract (see AGENTS.md). Backend imports only names from this module.

Changing these signatures requires agreement between Backend and AI.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.ai.persona import persona
from app.ai.persona.persona import Emergency, PersonaReply
from app.config import get_settings
from app.timeutil import KST


@dataclass(frozen=True)
class ChatMessage:
    sender_name: str
    text: str
    date: datetime  # UTC
    is_outgoing: bool  # True if sent by the logged-in user (or by auto reply)


class LLMError(Exception):
    """LLM call failed or timed out. Backend sends fallback_text and records last_error."""


# Base guidance applied to every chat room. Per-room guidance is appended via `instructions`.
# User-visible Korean; keep short. Spec 3.4.
_BASE_INSTRUCTIONS = (
    "너는 사용자 본인이다. 상대와 텔레그램 1:1 대화처럼 자연스럽게 한국어로 짧게 답해라. "
    "약속, 송금, 개인정보 제공처럼 사용자가 직접 결정해야 하는 일은 네가 알아서 하지 마라. "
    "대화에 없는 사실은 지어내지 마라."
)

# Spec 3.4: only the most recent 20 messages feed the model.
_HISTORY_LIMIT = 20


def _client() -> AsyncOpenAI:
    settings = get_settings()
    base_url = (settings.llm_base_url or "").rstrip("/")
    if not base_url:
        raise LLMError("LLM_BASE_URL이 설정되지 않았습니다.")
    # Spec 3.4: backend appends "/v1" to LLM_BASE_URL. vLLM runs without --api-key behind
    # an SSH tunnel, but the openai client requires some key value.
    return AsyncOpenAI(
        base_url=base_url + "/v1",
        api_key="EMPTY",
        timeout=settings.llm_timeout_sec,
    )


def _history_to_messages(history: list[ChatMessage]) -> list[dict]:
    # is_outgoing=True -> assistant (me); False -> user (partner). Spec 3.4.
    messages: list[dict] = []
    for m in history[-_HISTORY_LIMIT:]:
        if not m.text:
            continue
        role = "assistant" if m.is_outgoing else "user"
        messages.append({"role": role, "content": m.text})
    return messages


def _system_prompt(instructions: str) -> str:
    system = _BASE_INSTRUCTIONS
    extra = (instructions or "").strip()
    if extra:
        system += "\n\n[이 채팅방 지침]\n" + extra
    return system


async def generate_reply(history: list[ChatMessage], instructions: str) -> str:
    """Return a reply for the latest messages in `history` (oldest first)."""
    if get_settings().llm_use_stub:
        return "[stub] 지금은 답장이 어려워요. 나중에 연락드릴게요."
    settings = get_settings()
    if not settings.llm_model:
        raise LLMError("LLM_MODEL이 설정되지 않았습니다.")
    messages = [{"role": "system", "content": _system_prompt(instructions)}]
    messages += _history_to_messages(history)
    if len(messages) < 2:
        # No partner message to respond to.
        raise LLMError("답장을 만들 대화가 없습니다.")
    try:
        # Qwen3 defaults to thinking mode: slow, and emits  tags that break the
        # 30s budget and the short-reply goal. Off by default; chat templates that
        # do not reference enable_thinking simply ignore it.
        resp = await _client().chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
    except APITimeoutError as exc:
        raise LLMError("LLM 호출 시간 초과") from exc
    except APIConnectionError as exc:
        raise LLMError("LLM 서버에 연결할 수 없습니다") from exc
    except APIStatusError as exc:
        raise LLMError(f"LLM 호출 실패 (HTTP {exc.status_code})") from exc
    except APIError as exc:
        raise LLMError(f"LLM 호출 실패: {exc.__class__.__name__}") from exc

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise LLMError("LLM이 빈 응답을 반환했습니다.")
    return text


# --- Persona (style + memory) reply, ported from prototype/ -------------------------------
# The work directory belongs to one (user, chat); the backend creates it on ON and deletes it
# on OFF. Everything inside runs the blocking prototype code in a worker thread.


def _to_export(history: list[ChatMessage]) -> list[dict]:
    return [
        {
            "type": "message",
            "date": m.date.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S"),
            "from": m.sender_name,
            "text": m.text,
        }
        for m in history
    ]


def _to_messages(history: list[ChatMessage]) -> list[persona.Message]:
    return [
        persona.Message(m.date.astimezone(KST).strftime("%Y-%m-%d %H:%M"), m.sender_name, m.text)
        for m in history
        if m.text
    ]


def persona_ready(work_dir: str) -> bool:
    return persona.is_ready(work_dir)


async def analyze_chat(work_dir: str, history: list[ChatMessage], me: str, partner: str) -> None:
    """Save `history` (oldest first) as JSON in work_dir and extract style.md / memory.md.

    Takes a minute or two. Raises LLMError on failure.
    """
    if get_settings().llm_use_stub:
        return
    persona.write_history(work_dir, _to_export(history))
    try:
        await asyncio.to_thread(persona.analyze, work_dir, me, partner)
    except ValueError as exc:
        raise LLMError(str(exc)) from exc
    except Exception as exc:
        raise LLMError(f"대화 분석 실패: {exc.__class__.__name__}") from exc


async def generate_persona_reply(
    work_dir: str, history: list[ChatMessage], me: str, partner: str, instructions: str
) -> PersonaReply:
    """Reply in the owner's style using the analysis in work_dir. Raises LLMError on failure."""
    if get_settings().llm_use_stub:
        return PersonaReply("[stub] 지금은 답장이 어려워요. 나중에 연락드릴게요.", "")
    # The partner's trailing messages (after my last one) are the new message to answer.
    split = len(history)
    while split > 0 and not history[split - 1].is_outgoing:
        split -= 1
    new = [m.text for m in history[split:] if m.text]
    if not new:
        raise LLMError("답장할 상대 메시지가 없습니다.")
    before = _to_messages(history[:split])
    try:
        result = await asyncio.to_thread(
            persona.reply, work_dir, me, partner, before, "\n".join(new), instructions
        )
    except Exception as exc:
        raise LLMError(f"LLM 호출 실패: {exc.__class__.__name__}") from exc
    if not result.text:
        raise LLMError("LLM이 빈 응답을 반환했습니다.")
    return result


__all__ = [
    "ChatMessage",
    "LLMError",
    "Emergency",
    "PersonaReply",
    "analyze_chat",
    "generate_persona_reply",
    "generate_reply",
    "persona_ready",
]
