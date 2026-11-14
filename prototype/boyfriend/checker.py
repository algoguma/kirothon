"""상대 메시지가 올 때마다 Qwen3.8이 판단하는 2가지 체크

1. 비상상황 여부: 상대가 아프거나 다치거나 위험하면 → 나(주인)에게 알림
2. 답변 가능 여부: 기억/대화에 없는 사실을 물어서 지어내야만 답할 수 있으면 → 나에게 직접 질문
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import llm
from .style import parse_json

CHECK_SYSTEM = """너는 "{me}"의 연애 챗봇을 감시하는 판단기야. 챗봇은 {me}인 척 {partner}와 카톡하고 있어.
{partner}가 보낸 새 메시지를 보고 두 가지를 판단해서 JSON만 출력해.

1) emergency (비상상황): **새 메시지 자체**만 보고 판단해. 이전 대화에서 이미 나온 비상 내용은 다시 true로 하지 마
   (새 메시지가 증상 악화/새로운 위험을 말할 때만 true). {partner}가 실제로 아프거나, 다쳤거나, 사고/위험 상황이거나, 병원/응급,
   심한 우울, 자해, 극단적 표현, 안전 위협, 도움 요청 등 {me}가 직접 알아야 할 상황이면 true.
   - 몸이 아프다는 말은 가벼워도 true (예: "목이 칼칼해", "머리 아파", "배탈 났어", "감기 기운 있어" → true, severity "낮음").
   - 장난, 과장된 농담("배고파 죽겠다", "졸려 죽겠다" 등), 이미 다 나은 과거 얘기는 false.
   - severity: "낮음"(가벼운 몸살, 두통 등), "중간"(병원 갈 정도, 계속 아픔, 많이 힘들어함), "높음"(응급, 사고, 자해, 생명/안전 위험)
2) needs_owner (주인 확인 필요): 아래 순서로 판단해.
   a. needed_fact: 이 메시지에 답하려면 꼭 필요한 구체적 사실이 뭔지 적어. (필요 없으면 "없음")
   b. found: 그 사실이 <기억>, <최근 대화>, [지금 대화] 중 어디에든 있으면 거기서 찾은 내용을 적어. 없으면 "없음".
      ("✍️ 주인이 직접 알려준 정보"도 <기억>에 포함. 표현이 달라도 같은 내용이면 찾은 것)
   c. needs_owner = needed_fact가 있는데 found가 "없음"일 때만 true.
      "✍️ 주인이 직접 알려준 정보"와 [지금 대화]에서 {me}가 이미 답한 내용은 확정된 사실이야.
      그걸로 답할 수 있으면 "바뀔 수도 있다", "재확인 필요" 같은 추측으로 true 하지 마.
   - false인 예: "뭐해?", "밥 먹었어?", "보고싶어", "사랑해?", 리액션/감정/잡담
     (현재 기분이나 가벼운 근황은 챗봇이 자연스럽게 둘러댈 수 있으므로 사실이 필요 없음)
   - true인 예: <기억>에 없는 약속 날짜/시간/장소 확인, 새 약속 수락/거절 결정, {me}의 과거 행동/일정 질문,
     돈/선물/가족 관련 결정처럼 {me}가 책임져야 하는 답
   - 새 메시지가 비상상황이면 needs_owner는 false로 해 (비상 알림으로 주인에게 이미 전달됨)
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


def _bool(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "yes", "1", "예")


def _in_message(evidence: str, text: str) -> bool:
    """비상 근거가 '새 메시지'에 실제로 있는지 (이전 대화의 비상이 다시 잡히는 것 방지)"""
    ev = re.sub(r"[\s\"'“”‘’.,!?~ㅠㅜ]", "", evidence or "")
    tx = re.sub(r"[\s\"'“”‘’.,!?~ㅠㅜ]", "", text)
    if len(ev) < 2:
        return False
    return ev in tx or (len(tx) >= 2 and tx in ev) or any(ev[i:i + 4] in tx for i in range(max(1, len(ev) - 3)))


class Checker:
    def __init__(self, me: str, partner: str, memory_md: str, recent_text: str):
        self.me, self.partner = me, partner
        self.update(memory_md, recent_text)

    def update(self, memory_md: str, recent_text: str):
        # 시스템 프롬프트가 매번 같아서 vLLM prefix cache로 빠르게 처리됨
        self.system = CHECK_SYSTEM.format(me=self.me, partner=self.partner,
                                          memory=memory_md.strip(), recent=recent_text)

    def check(self, history: list[dict], new_text: str) -> CheckResult:
        convo = "\n".join(f"{self.partner if h['role'] == 'user' else self.me}: {h['content']}"
                          for h in history[-12:])
        user = f"[지금 대화]\n{convo}\n\n[{self.partner}의 새 메시지]\n{new_text}"
        try:
            raw = llm.chat([{"role": "system", "content": self.system}, {"role": "user", "content": user}],
                           temperature=0.0, max_tokens=500, json_mode=True)
            d = parse_json(raw)
        except Exception as e:  # 판단 실패 시 대화는 계속 (안전하게 기본값)
            return CheckResult(reason=f"판단 실패: {e}")
        emergency = _bool(d.get("emergency")) and _in_message(str(d.get("emergency_evidence") or ""), new_text)
        return CheckResult(
            emergency=emergency, severity=str(d.get("severity") or ""),
            emergency_reason=str(d.get("emergency_reason") or ""),
            needs_owner=_bool(d.get("needs_owner")), owner_question=str(d.get("owner_question") or ""),
            reason=str(d.get("reason") or ""), raw=d)
