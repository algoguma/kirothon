# ruff: noqa: E501  (Korean prompt text)
"""Reply as the owner using style.md + memory.md + recent chat (ported from prototype/boyfriend).

Changes from the prototype:
- The persona is "the owner himself", not a boyfriend, and the per-chat instructions are appended.
- Recent chat comes from Telegram on every reply, so there is no in-memory conversation state.
- Analysis results live in a per-chat work directory that the backend deletes when auto reply is off.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import llm
from .checker import check
from .memory import extract_memory, memory_to_markdown
from .parser import Message, load_chat, speakers, to_transcript
from .style import extract_style, style_to_markdown

HISTORY_FILE = "history.json"
MAX_MESSAGES = 1000  # analysis input
STYLE_MESSAGES = 500  # most recent N of them for style
RECENT_RAW = 150  # raw recent messages in the reply prompt

SYSTEM_PROMPT = """너는 지금부터 "{me}" 본인이야. "{partner}"와 텔레그램 1:1 대화를 하고 있어.
AI, 어시스턴트, 언어모델이라는 사실은 절대 드러내지 마. 진짜 {me}처럼 대화해.

<말투>
{style}
</말투>

<기억>
{memory}
</기억>

[규칙]
- <말투>를 그대로 따라 해. 말 높이, 호칭, 웃음(ㅋㅋ/ㅎㅎ), 기호, 자주 쓰는 표현, 띄어쓰기/오타 습관까지.
- <기억>에 있는 약속, 계획, 있었던 일, 상대 정보를 기억하고 있어. 관련된 얘기가 나오면 구체적으로(장소, 시간, 누구와) 말해.
- <기억>과 아래 대화에 없는 사실은 지어내지 마.
- 약속, 송금, 개인정보 제공처럼 {me}가 직접 결정해야 하는 일은 네가 정하지 마.
- 짧게. 한 줄이 메시지 하나이고, 보통 1~3줄. 같은 말 반복하지 마.
- 설명문, 목록, 마크다운, 이름표("{me}:")는 쓰지 마.
- 메시지 끝에 (속마음 메모: ...)가 붙어 있으면 너만 보는 메모야. 따르되 절대 언급하지 마.
{instructions}
[직전 대화 원문 (최근 {n_recent}개)]
{recent}
"""

EMERGENCY_HINT = (
    "(속마음 메모: {partner}가 지금 비상상황이야 — {reason}. 장난이나 ㅋㅋ는 빼고 진심으로 걱정해 줘. "
    "상태를 구체적으로 물어보고, 심하면 병원이나 119를 권해. 2~4줄로 짧게. 기억에 없는 일은 지어내지 마.)"
)

# Owner confirmation needed: give only the style, so there is nothing to make things up from.
HOLD_SYSTEM = """너는 "{me}"야. "{partner}"와 채팅 중인데, {partner}가 물어본 걸 너는 지금 확실히 몰라서 확인해봐야 해.
아래 말투로 "확인해보고 알려준다"는 뜻만 1~2줄로 짧게 답해.
- 질문에 대한 답, 추측, 이유, 사실(시간/장소/했다/안했다 등)은 절대 말하지 마.
- 이름표, 마크다운 없이.

<말투>
{style}
</말투>"""


@dataclass(frozen=True)
class PersonaReply:
    text: str
    note: str | None  # emergency / owner-question notice for the owner, if any


def is_ready(work_dir: str) -> bool:
    return all(os.path.exists(os.path.join(work_dir, n)) for n in ("style.md", "memory.md"))


def write_history(work_dir: str, msgs: list[dict]) -> str:
    """Save the chat as Telegram-export-style JSON (the prototype parser's JSON format)."""
    os.makedirs(work_dir, exist_ok=True)
    path = os.path.join(work_dir, HISTORY_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"messages": msgs}, f, ensure_ascii=False)
    return path


def analyze(work_dir: str, me: str, partner: str) -> None:
    """Style + memory extraction in parallel; writes style.md and memory.md. Blocking."""
    msgs = load_chat(os.path.join(work_dir, HISTORY_FILE), MAX_MESSAGES)
    names = speakers(msgs)
    if me not in names or partner not in names:
        raise ValueError("분석할 대화가 부족합니다.")
    with ThreadPoolExecutor(2) as ex:
        f_style = ex.submit(extract_style, msgs[-STYLE_MESSAGES:], me, partner)
        f_mem = ex.submit(extract_memory, msgs, me, partner)
        style, memory = f_style.result(), f_mem.result()
    # memory.md is written last: is_ready() needs both files.
    with open(os.path.join(work_dir, "style.md"), "w", encoding="utf-8") as f:
        f.write(style_to_markdown(style))
    with open(os.path.join(work_dir, "memory.md"), "w", encoding="utf-8") as f:
        f.write(memory_to_markdown(memory, me, partner))


def _clean(text: str, me: str) -> str:
    text = re.sub(rf"^\s*{re.escape(me)}\s*[:：]\s*", "", text, flags=re.M)
    text = re.sub(r"\(속마음 메모:.*?\)", "", text, flags=re.S)
    text = re.sub(r"[*#`]+", "", text)
    lines, seen = [], set()
    for line in (raw.strip() for raw in text.splitlines()):
        if line and line not in seen:
            lines.append(line)
            seen.add(line)
    return "\n".join(lines)


def _generate(messages: list[dict], me: str) -> str:
    return _clean("".join(llm.stream(messages)), me)


def reply(
    work_dir: str,
    me: str,
    partner: str,
    before: list[Message],
    new_text: str,
    instructions: str,
) -> PersonaReply:
    """Blocking. `before` is the chat before the partner's new messages (oldest first)."""
    with open(os.path.join(work_dir, "style.md"), encoding="utf-8") as f:
        style_md = f.read().strip()
    with open(os.path.join(work_dir, "memory.md"), encoding="utf-8") as f:
        memory_md = f.read().strip()
    recent = before[-RECENT_RAW:]

    res = check(me, partner, memory_md, to_transcript(recent[-60:]), new_text)
    if res.needs_owner and not res.emergency:
        messages = [
            {
                "role": "system",
                "content": HOLD_SYSTEM.format(me=me, partner=partner, style=style_md),
            },
            {"role": "user", "content": new_text},
        ]
        question = res.owner_question or f'{partner}: "{new_text}" — 어떻게 답할까요?'
        return PersonaReply(_generate(messages, me), f"[확인 필요] {question}")

    extra = (instructions or "").strip()
    system = SYSTEM_PROMPT.format(
        me=me,
        partner=partner,
        style=style_md,
        memory=memory_md,
        instructions=f"\n[이 채팅방 지침]\n{extra}\n" if extra else "",
        n_recent=len(recent),
        recent=to_transcript(recent),
    )
    content = new_text
    note = None
    if res.emergency:
        reason = res.emergency_reason or "몸/마음 상태가 안 좋음"
        content += "\n\n" + EMERGENCY_HINT.format(partner=partner, reason=reason)
        note = f"[비상 {res.severity or ''}] {reason}".replace("  ", " ")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    return PersonaReply(_generate(messages, me), note)
