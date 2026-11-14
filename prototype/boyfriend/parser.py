"""대화 파일 파서 (카카오톡 txt / JSON).

txt (카카오톡 '대화 내보내기')
- PC:     2024. 8. 4. 13:00, 이름 : 메시지
- 모바일: 2024년 8월 4일 오후 1:00, 이름 : 메시지
날짜 구분선, 저장 정보 등은 무시하고, 형식에 안 맞는 줄은 직전 메시지의 줄바꿈으로 취급합니다.

JSON (텔레그램 내보내기 형식 등)
- {"messages": [{"type": "message", "date": "2024-08-04T13:00:00", "from": "이름", "text": "메시지"}, ...]}
- 메시지 리스트만 있는 [...] 형식도 지원
- text가 문자열 조각 리스트인 경우, 서비스 메시지, 사진/스티커만 있는 메시지도 처리
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass

from . import config

PC_RE = re.compile(r"^(\d{4})\. (\d{1,2})\. (\d{1,2})\. (\d{1,2}):(\d{2}), (.+?) : (.*)$")
MOBILE_RE = re.compile(r"^(\d{4})년 (\d{1,2})월 (\d{1,2})일 (오전|오후) (\d{1,2}):(\d{2}), (.+?) : (.*)$")
DATE_HEADER_RE = re.compile(r"^(-+ )?\d{4}년 \d{1,2}월 \d{1,2}일 \S+요일( -+)?$")
HEADER_PREFIXES = ("Talk_", "저장한 날짜", "카카오톡 대화")

# 텍스트가 아닌 메시지 (말투 학습에서 제외)
MEDIA = {"사진", "동영상", "이모티콘", "파일", "음성메시지", "삭제된 메시지입니다.", "메시지가 삭제되었습니다."}


@dataclass
class Message:
    time: str
    speaker: str
    text: str

    @property
    def is_media(self) -> bool:
        t = self.text.strip()
        if t.startswith("[") and t.endswith("]"):  # JSON 형식의 "[사진]", "[이모티콘]" 등
            t = t[1:-1].strip()
        return not t or t in MEDIA or t == "스티커" or re.fullmatch(r"사진 \d+장", t) is not None


def _match(line: str):
    m = PC_RE.match(line)
    if m:
        y, mo, d, h, mi, spk, txt = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d} {int(h):02d}:{mi}", spk, txt
    m = MOBILE_RE.match(line)
    if m:
        y, mo, d, ampm, h, mi, spk, txt = m.groups()
        h = int(h) % 12 + (12 if ampm == "오후" else 0)
        return f"{y}-{int(mo):02d}-{int(d):02d} {h:02d}:{mi}", spk, txt
    return None


def parse_kakao(text: str, limit: int | None = config.MAX_MESSAGES) -> list[Message]:
    """카톡 txt 내용을 Message 리스트로. 앞에서부터 limit개(텍스트 메시지 기준)만 읽습니다. None이면 전부."""
    msgs: list[Message] = []
    for raw in text.lstrip("﻿").splitlines():
        line = raw.rstrip("\r")
        if not line.strip() or DATE_HEADER_RE.match(line) or line.startswith(HEADER_PREFIXES):
            continue
        hit = _match(line)
        if hit:
            msg = Message(*hit)
            if msg.is_media:
                continue
            if limit and len(msgs) >= limit:
                break
            msgs.append(msg)
        elif msgs:  # 여러 줄 메시지의 이어지는 줄
            msgs[-1].text += "\n" + line
    return msgs


def _json_text(t) -> str:
    """텔레그램 text 필드: 문자열 또는 [문자열 | {"type":..., "text":...}] 조각 리스트"""
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return "".join(x if isinstance(x, str) else str(x.get("text", "")) for x in t)
    return "" if t is None else str(t)


def _json_time(m: dict) -> str:
    d = m.get("date") or m.get("time") or m.get("timestamp") or ""
    if isinstance(d, (int, float)) or (isinstance(d, str) and d.isdigit()):
        import datetime
        return datetime.datetime.fromtimestamp(int(d)).strftime("%Y-%m-%d %H:%M")
    return str(d).replace("T", " ")[:16]  # "2024-08-04T13:00:00" → "2024-08-04 13:00"


def parse_json(text: str, limit: int | None = config.MAX_MESSAGES) -> list[Message]:
    """JSON 대화를 Message 리스트로. 앞에서부터 limit개(텍스트 메시지 기준)만 읽습니다."""
    data = json.loads(text.lstrip("﻿"))
    items = data.get("messages", []) if isinstance(data, dict) else data
    msgs: list[Message] = []
    for m in items:
        if not isinstance(m, dict) or m.get("type", "message") != "message":
            continue  # 서비스 메시지(입장/고정 등) 제외
        speaker = m.get("from") or m.get("sender") or m.get("user") or m.get("name")
        body = _json_text(m.get("text", m.get("message", m.get("content"))))
        if not speaker or not body.strip():
            continue  # 작성자 없음 / 사진·스티커만 있는 메시지
        msg = Message(_json_time(m), str(speaker), body)
        if msg.is_media:
            continue
        if limit and len(msgs) >= limit:
            break
        msgs.append(msg)
    return msgs


def load_kakao(path: str, limit: int | None = config.MAX_MESSAGES) -> list[Message]:
    """대화 파일 읽기 (.json이거나 내용이 JSON이면 JSON 파서, 아니면 카카오톡 txt 파서)"""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    if path.lower().endswith(".json") or text.lstrip()[:1] in ("{", "["):
        return parse_json(text, limit)
    return parse_kakao(text, limit)


load_chat = load_kakao  # 형식 무관 별칭


def speakers(msgs: list[Message]) -> list[str]:
    """메시지 많은 순 화자 목록"""
    return [s for s, _ in Counter(m.speaker for m in msgs).most_common()]


def to_transcript(msgs: list[Message]) -> str:
    return "\n".join(f"{m.speaker}: {m.text}" for m in msgs)


def to_turns(msgs: list[Message], me: str) -> list[dict]:
    """연속 메시지를 한 턴으로 묶어 OpenAI chat 형식(user=상대, assistant=나)으로 변환"""
    turns: list[dict] = []
    for m in msgs:
        role = "assistant" if m.speaker == me else "user"
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n" + m.text
        else:
            turns.append({"role": role, "content": m.text})
    while turns and turns[0]["role"] == "assistant":  # user 턴으로 시작하게
        turns.pop(0)
    return turns
