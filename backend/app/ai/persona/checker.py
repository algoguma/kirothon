# ruff: noqa: E501  (Korean prompt text)
"""Per-message checks: emergency and "owner must answer" (ported from prototype/boyfriend/checker.py)."""

import re
from dataclasses import dataclass, field

from . import llm
from .style import parse_json

CHECK_SYSTEM = """너는 "{me}"의 자동 답장 챗봇을 감시하는 판단기야. 챗봇은 {me}인 척 {partner}와 1:1 채팅을 하고 있어.
{partner}가 보낸 새 메시지를 보고 두 가지를 판단해서 JSON만 출력해.

1) emergency (비상상황): **새 메시지 자체**만 보고 판단해. 이전 대화에서 이미 나온 비상 내용은 다시 true로 하지 마
   (새 메시지가 증상 악화/새로운 위험을 말할 때만 true). {partner}가 실제로 아프거나, 다쳤거나, 사고/위험 상황이거나, 병원/응급,
   심한 우울, 자해, 극단적 표현, 안전 위협, 도움 요청 등 {me}가 직접 알아야 할 상황이면 true.
   - 몸이 아프다는 말은 가벼워도 true (예: "머리 아파", "배탈 났어" → true, severity "낮음").
   - 장난, 과장된 농담("배고파 죽겠다" 등), 이미 다 나은 과거 얘기는 false.
   - severity: "낮음", "중간"(병원 갈 정도, 계속 아픔), "높음"(응급, 사고, 자해, 생명/안전 위험)
2) needs_owner (주인 확인 필요): 아래 순서로 판단해.
   a. needed_fact: 이 메시지에 답하려면 꼭 필요한 구체적 사실 (필요 없으면 "없음")
   b. found: 그 사실이 <기억>, <최근 대화> 중 어디에든 있으면 찾은 내용, 없으면 "없음"
   c. needs_owner = needed_fact가 있는데 found가 "없음"일 때만 true.
   - false인 예: "뭐해?", "밥 먹었어?", 리액션/감정/잡담 (자연스럽게 둘러댈 수 있음)
   - true인 예: <기억>에 없는 약속 날짜/시간/장소 확인, 새 약속 수락/거절 결정, {me}의 과거 행동/일정 질문,
     돈/선물/가족 관련 결정처럼 {me}가 책임져야 하는 답
   - 새 메시지가 비상상황이면 needs_owner는 false
   - owner_question: needs_owner가 true일 때만, {me}에게 물어볼 짧고 구체적인 질문

출력 형식 (키 순서대로):
{{"emergency_evidence": "새 메시지에서 비상의 근거가 되는 표현을 그대로 인용 (없으면 빈 문자열)",
  "emergency": false, "severity": "", "emergency_reason": "",
  "needed_fact": "", "found": "", "needs_owner": false, "owner_question": "", "reason": "판단 근거 한 줄"}}

<기억>
{memory}
</기억>

<최근 대화>
{recent}
</최근 대화>
"""


@dataclass
class CheckResult:
    emergency: bool = False
    severity: str = ""
    emergency_reason: str = ""
    needs_owner: bool = False
    owner_question: str = ""
    reason: str = ""
    raw: dict = field(default_factory=dict)


def _bool(v: object) -> bool:
    return v is True or str(v).strip().lower() in ("true", "yes", "1", "예")


def _in_message(evidence: str, text: str) -> bool:
    """Is the emergency evidence really quoted from the new message?"""
    ev = re.sub(r"[\s\"'“”‘’.,!?~ㅠㅜ]", "", evidence or "")
    tx = re.sub(r"[\s\"'“”‘’.,!?~ㅠㅜ]", "", text)
    if len(ev) < 2:
        return False
    return (
        ev in tx
        or (len(tx) >= 2 and tx in ev)
        or any(ev[i : i + 4] in tx for i in range(max(1, len(ev) - 3)))
    )


def check(me: str, partner: str, memory_md: str, recent: str, new_text: str) -> CheckResult:
    system = CHECK_SYSTEM.format(me=me, partner=partner, memory=memory_md.strip(), recent=recent)
    user = f"[{partner}의 새 메시지]\n{new_text}"
    try:
        raw = llm.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=500,
            json_mode=True,
        )
        d = parse_json(raw)
    except Exception as e:  # a failed check must not block the reply
        return CheckResult(reason=f"판단 실패: {type(e).__name__}")
    emergency = _bool(d.get("emergency")) and _in_message(
        str(d.get("emergency_evidence") or ""), new_text
    )
    return CheckResult(
        emergency=emergency,
        severity=str(d.get("severity") or ""),
        emergency_reason=str(d.get("emergency_reason") or ""),
        needs_owner=_bool(d.get("needs_owner")),
        owner_question=str(d.get("owner_question") or ""),
        reason=str(d.get("reason") or ""),
        raw=d,
    )
