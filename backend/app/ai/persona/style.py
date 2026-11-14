"""Extract the owner's speaking style (ported from prototype/boyfriend/style.py)."""

import json
import re

from . import llm
from .parser import Message, to_transcript

STYLE_PROMPT = """너는 한국어 채팅 말투 분석 전문가야.
아래 대화에서 "{me}"의 말투만 분석해서 JSON으로 출력해. ("{partner}"는 대화 상대야)

반드시 아래 키를 가진 JSON 하나만 출력해:
{{
  "summary": "{me}의 말투를 2~3문장으로 요약",
  "speech_level": "반말/존댓말/섞어씀 + 설명",
  "partner_nickname": "{me}가 {partner}를 부르는 호칭들 (없으면 빈 문자열)",
  "self_reference": "자기 자신을 부르는 말 (예: 나, 저 등)",
  "endings": ["자주 쓰는 어미/말끝 5~10개"],
  "laughter": "ㅋㅋ/ㅎㅎ 등 웃음 표현 습관 (종류, 길이)",
  "emoji_and_symbols": "이모지, 이모티콘, !!!, ???, ~ 등 기호 사용 습관",
  "frequent_expressions": ["자주 쓰는 단어/감탄사/표현 10개 이상"],
  "message_length": "한 메시지 길이와 여러 개로 끊어 보내는 습관",
  "affection_style": "리액션, 공감하는 방식",
  "typos_and_spacing": "맞춤법/띄어쓰기/오타/줄임말 습관",
  "sample_lines": ["{me}가 실제로 한 말 중 말투가 잘 드러나는 문장 8개 (원문 그대로)"]
}}

[대화]
{transcript}
"""

LABELS = {
    "summary": "요약",
    "speech_level": "말 높이",
    "partner_nickname": "상대 호칭",
    "self_reference": "자기 지칭",
    "endings": "자주 쓰는 말끝",
    "laughter": "웃음",
    "emoji_and_symbols": "이모지/기호",
    "frequent_expressions": "자주 쓰는 표현",
    "message_length": "메시지 길이",
    "affection_style": "리액션",
    "typos_and_spacing": "맞춤법/줄임말",
    "sample_lines": "실제 예시 문장",
}


def parse_json(text: str) -> dict:
    """Extract JSON from model output (allows code fences and chatter). ValueError on failure."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("JSON not found") from None
        return json.loads(m.group(0))


def extract_style(msgs: list[Message], me: str, partner: str) -> dict:
    prompt = STYLE_PROMPT.format(me=me, partner=partner, transcript=to_transcript(msgs))
    raw = llm.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
        json_mode=True,
        long=True,
    )
    try:
        profile = parse_json(raw)
    except ValueError:
        profile = {"summary": raw}
    profile["_me"], profile["_count"] = me, len(msgs)
    profile["_range"] = f"{msgs[0].time} ~ {msgs[-1].time}" if msgs else ""
    return profile


def style_to_markdown(p: dict) -> str:
    out = [
        f"# 말투 프로필: {p.get('_me', '')}",
        f"> 최근 대화 {p.get('_count', '?')}개 ({p.get('_range', '')})에서 추출",
        "",
    ]
    for k, label in LABELS.items():
        v = p.get(k)
        if not v:
            continue
        out.append(f"## {label}")
        out += [f"- {x}" for x in v] if isinstance(v, list) else [str(v)]
        out.append("")
    return "\n".join(out).strip() + "\n"
