"""Backend <-> AI contract (see AGENTS.md). Backend imports only names from this module.

Changing these signatures requires agreement between Backend and AI.
"""

from dataclasses import dataclass
from datetime import datetime

from app.config import get_settings


@dataclass(frozen=True)
class ChatMessage:
    sender_name: str
    text: str
    date: datetime  # UTC
    is_outgoing: bool  # True if sent by the logged-in user (or by auto reply)


class LLMError(Exception):
    """LLM call failed or timed out. Backend sends fallback_text and records last_error."""


async def generate_reply(api_key: str, history: list[ChatMessage], instructions: str) -> str:
    """Return a reply for the latest messages in `history` (oldest first)."""
    if get_settings().llm_use_stub:
        return "[stub] 지금은 답장이 어려워요. 나중에 연락드릴게요."
    raise LLMError("generate_reply is not implemented yet")  # TODO(AI)


async def verify_api_key(api_key: str) -> None:
    """Check the key with GET {LLM_BASE_URL}/v1/models. Raise LLMError on failure."""
    if get_settings().llm_use_stub:
        if not api_key:
            raise LLMError("empty api key")
        return
    raise LLMError("verify_api_key is not implemented yet")  # TODO(AI)


__all__ = ["ChatMessage", "LLMError", "generate_reply", "verify_api_key"]
