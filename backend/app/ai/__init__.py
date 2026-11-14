"""Backend <-> AI contract (see AGENTS.md). Backend imports only names from this module.

Changing these signatures requires agreement between Backend and AI.
"""

from dataclasses import dataclass
from datetime import datetime

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.config import get_settings


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


def _client(api_key: str) -> AsyncOpenAI:
    settings = get_settings()
    base_url = (settings.llm_base_url or "").rstrip("/")
    if not base_url:
        raise LLMError("LLM_BASE_URL이 설정되지 않았습니다.")
    # Spec 3.4: backend appends "/v1" to LLM_BASE_URL.
    return AsyncOpenAI(
        base_url=base_url + "/v1",
        api_key=api_key or "EMPTY",
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


async def generate_reply(api_key: str, history: list[ChatMessage], instructions: str) -> str:
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
        resp = await _client(api_key).chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
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


async def verify_api_key(api_key: str) -> None:
    """Check the key with GET {LLM_BASE_URL}/v1/models. Raise LLMError on failure."""
    if get_settings().llm_use_stub:
        if not api_key:
            raise LLMError("empty api key")
        return
    try:
        await _client(api_key).models.list()
    except APITimeoutError as exc:
        raise LLMError("LLM 연결 시간 초과") from exc
    except APIConnectionError as exc:
        raise LLMError("LLM 서버에 연결할 수 없습니다") from exc
    except APIStatusError as exc:
        raise LLMError(f"LLM 키 확인 실패 (HTTP {exc.status_code})") from exc
    except APIError as exc:
        raise LLMError(f"LLM 키 확인 실패: {exc.__class__.__name__}") from exc


__all__ = ["ChatMessage", "LLMError", "generate_reply", "verify_api_key"]
