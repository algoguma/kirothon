"""말투(style.md) + 기억(memory.md) + 최근 대화 원문으로 Qwen3.8이 남자친구 역할을 합니다.

메시지가 오면
  1) Checker(Qwen3.8)가 비상상황 / 주인 확인 필요 여부를 판단하고
  2) 판단 결과에 맞춰 답장 톤을 바꾸거나(비상), 지어내지 않고 보류한 뒤 주인에게 묻습니다(확인 필요).
  3) 주인이 답하면 그 내용을 내 말투로 상대에게 보내고, memory.md에 추가해 계속 기억합니다.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from typing import Iterator

from . import llm
from .checker import Checker, CheckResult
from .parser import Message, to_transcript

SYSTEM_PROMPT = """너는 지금부터 "{me}"야. "{partner}"의 다정한 남자친구로서 카카오톡을 하고 있어.
AI, 어시스턴트, 언어모델이라는 사실은 절대 드러내지 마. 진짜 사람처럼 대화해.
지금은 아래 과거 대화의 마지막 시점({last_time}) 바로 뒤에 이어지는 대화야.

<말투>
{style}
</말투>

<기억>
{memory}
</기억>

[규칙]
- <말투>를 그대로 따라 해. 말 높이, 호칭, 웃음(ㅋㅋ/ㅎㅎ), 기호, 자주 쓰는 표현, 띄어쓰기/오타 습관까지.
- <기억>에 있는 약속, 계획, 있었던 일, 상대 정보를 기억하고 있어. 관련된 얘기가 나오면 먼저 꺼내서 구체적으로(장소, 시간, 누구와) 말해.
- <기억>과 아래 대화에 없는 사실은 지어내지 마.
- 카톡처럼 짧게. 한 줄이 메시지 하나이고, 보통 1~5줄로 끊어서 보내. 같은 말 반복하지 마.
- 설명문, 목록, 마크다운, 이름표("{me}:")는 쓰지 마.
- 상대 말에 먼저 리액션하고 공감해 줘. 애정 표현은 자연스럽게.
- 메시지 끝에 (속마음 메모: ...)가 붙어 있으면 그건 상대가 쓴 게 아니라 너만 보는 메모야. 따르되 절대 언급하지 마.

[직전 대화 원문 (최근 {n_recent}개)]
{recent}
"""

EMERGENCY_HINT = ("(속마음 메모: {partner}가 지금 비상상황이야 — {reason}. 장난이나 ㅋㅋ는 빼고 진심으로 걱정해 줘. "
                  "상태를 구체적으로 물어보고, 심하면 병원이나 119를 권하고, 바로 연락하거나 가겠다고 해. "
                  "3~6줄로 짧게, 질문은 한두 개만. 기억에 없는 일은 지어내지 마.)")
# 확인 필요 시: 기억/과거 대화 없이 말투만 주고 '보류 멘트'만 생성 (지어낼 재료 자체를 안 줌)
HOLD_SYSTEM = """너는 "{me}"야. "{partner}"와 카톡 중인데, {partner}가 물어본 걸 너는 지금 확실히 몰라서 확인해봐야 해.
아래 말투로 "확인해보고 알려준다"는 뜻만 1~2줄로 짧게 답해.
- 질문에 대한 답, 추측, 이유, 사실(시간/장소/했다/안했다 등)은 절대 말하지 마.
- 이름표, 마크다운 없이 카톡처럼.

<말투>
{style}
</말투>"""
OWNER_ANSWER_HINT = ("(속마음 메모: 이건 {partner}의 새 메시지가 아니야. 아까 {partner}가 \"{question}\"라고 물어봐서 "
                     "확인해 본다고 했었지. 확인 결과: \"{answer}\". 이제 네가 먼저 \"확인해봤는데\" 같은 느낌으로 "
                     "이 결과를 {partner}에게 알려줘. 질문을 되풀이하지 말고, 결과 내용(시간/장소 등)은 바꾸지 마.)")


class Boyfriend:
    def __init__(self, me: str, partner: str, style_md: str, memory_md: str,
                 recent: list[Message], max_history: int = 30, out_dir: str | None = None):
        self.me, self.partner = me, partner
        self.style_md, self.memory_md = style_md.strip(), memory_md.strip()
        self.recent = recent
        self.out_dir = out_dir
        self.history: list[dict] = []
        self.max_history = max_history
        self.pending: dict | None = None   # 주인 확인 대기 중인 질문
        self.alerts: list[dict] = []       # 비상상황 기록
        self.checker = Checker(me, partner, self.memory_md, to_transcript(recent[-60:]))
        self._build_system()

    # ---------- 프롬프트 ----------
    def _build_system(self):
        self.system = SYSTEM_PROMPT.format(
            me=self.me, partner=self.partner, style=self.style_md, memory=self.memory_md,
            last_time=self.recent[-1].time if self.recent else "알 수 없음",
            n_recent=len(self.recent), recent=to_transcript(self.recent))

    def reset(self):
        self.history, self.pending = [], None

    def _messages(self, user_text: str, hint: str = "") -> list[dict]:
        content = f"{user_text}\n\n{hint}" if hint else user_text
        return [{"role": "system", "content": self.system},
                *self.history[-self.max_history:],
                {"role": "user", "content": content}]

    @staticmethod
    def clean(text: str, me: str) -> str:
        text = re.sub(rf"^\s*{re.escape(me)}\s*[:：]\s*", "", text, flags=re.M)
        text = re.sub(r"\(속마음 메모:.*?\)", "", text, flags=re.S)
        text = re.sub(r"[*#`]+", "", text)
        lines, seen = [], set()
        for l in (l.strip() for l in text.splitlines()):
            if l and l not in seen:  # 같은 줄 반복 제거
                lines.append(l)
                seen.add(l)
        return "\n".join(lines)

    def _stream(self, messages: list[dict]) -> Iterator[str]:
        acc = ""
        for tok in llm.stream(messages):
            acc += tok
            yield self.clean(acc, self.me)

    # ---------- 1단계: 판단 ----------
    def check(self, user_text: str) -> CheckResult:
        res = self.checker.check(self.history, user_text)
        if res.emergency:
            alert = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "message": user_text,
                     "severity": res.severity, "reason": res.emergency_reason}
            self.alerts.append(alert)
            self._log("alerts.jsonl", alert)
        if res.needs_owner and not res.emergency:  # 비상이면 비상 알림이 우선
            self.pending = {"partner_message": user_text,
                            "question": res.owner_question or f"{self.partner}: \"{user_text}\" — 어떻게 답할까요?"}
        return res

    # ---------- 2단계: 답장 ----------
    def reply_stream(self, user_text: str, check: CheckResult | None = None) -> Iterator[str]:
        """판단 결과에 맞춰 답장 생성 (누적 문자열 스트리밍)"""
        if check and check.emergency:
            hint = EMERGENCY_HINT.format(partner=self.partner, reason=check.emergency_reason or "몸/마음 상태가 안 좋음")
            messages = self._messages(user_text, hint)
        elif check and check.needs_owner and self.pending:
            messages = [{"role": "system", "content": HOLD_SYSTEM.format(
                            me=self.me, partner=self.partner, style=self.style_md)},
                        *self.history[-4:], {"role": "user", "content": user_text}]
        else:
            messages = self._messages(user_text)
        final = ""
        for final in self._stream(messages):
            yield final
        self.history += [{"role": "user", "content": user_text},
                         {"role": "assistant", "content": final}]

    def reply(self, user_text: str) -> tuple[CheckResult, list[str]]:
        """판단 + 답장 (CLI용)"""
        res = self.check(user_text)
        final = ""
        for final in self.reply_stream(user_text, res):
            pass
        return res, final.splitlines()

    # ---------- 3단계: 주인 답변 ----------
    def answer_owner_stream(self, answer: str) -> Iterator[str]:
        """주인이 답한 내용을 내 말투로 상대에게 보내고, memory.md에 추가"""
        if not self.pending:
            raise ValueError("확인 대기 중인 질문이 없습니다.")
        q = self.pending
        self.pending = None
        self.add_memory(f"{self.partner}의 질문 \"{q['partner_message']}\" → {answer}")
        # 상대 질문이 대화 기록에 없으면(판단만 하고 답장 전인 경우 등) 넣어서 흐름을 맞춤
        if not any(h["role"] == "user" and h["content"] == q["partner_message"] for h in self.history[-6:]):
            self.history += [{"role": "user", "content": q["partner_message"]},
                             {"role": "assistant", "content": "잠깐만 확인해보고 알려줄게"}]
        hint = OWNER_ANSWER_HINT.format(partner=self.partner, question=q["partner_message"], answer=answer)
        # 상대의 새 메시지가 아니라 내가 이어서 보내는 메시지이므로 history에는 assistant 발화만 추가
        msgs = [{"role": "system", "content": self.system}, *self.history[-self.max_history:],
                {"role": "user", "content": hint}]
        final = ""
        for final in self._stream(msgs):
            final = "\n".join(l for l in final.splitlines() if "확인해보고 알려줄게" not in l)  # 보류 멘트 반복 제거
            yield final
        self.history.append({"role": "assistant", "content": final})

    def add_memory(self, fact: str):
        """주인이 알려준 정보를 memory.md에 추가하고 프롬프트에 즉시 반영"""
        header = "## ✍️ 주인이 직접 알려준 정보"
        line = f"- [{datetime.date.today()}] {fact}"
        if header in self.memory_md:
            self.memory_md = self.memory_md.replace(header, f"{header}\n{line}", 1)
        else:  # 가장 중요한 최신 정보라 제목/설명 바로 아래(맨 위)에 둠
            lines = self.memory_md.splitlines()
            at = next((i + 1 for i, l in enumerate(lines) if l.startswith(">")), 1)
            lines[at:at] = ["", header, line]
            self.memory_md = "\n".join(lines)
        self._build_system()
        self.checker.update(self.memory_md, to_transcript(self.recent[-60:]))
        if self.out_dir:
            with open(os.path.join(self.out_dir, "memory.md"), "w", encoding="utf-8") as f:
                f.write(self.memory_md + "\n")

    def _log(self, name: str, obj: dict):
        if self.out_dir:
            with open(os.path.join(self.out_dir, name), "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
