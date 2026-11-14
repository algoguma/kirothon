"""Chat export parsing (ported from prototype/boyfriend/parser.py, JSON format only).

The backend writes the Telegram history as a Telegram-export-style JSON:
{"messages": [{"type": "message", "date": "2026-11-14T10:23:00", "from": "이름", "text": "..."}]}
"""

import json
import re
from collections import Counter
from dataclasses import dataclass

# Non-text messages are excluded from style analysis.
MEDIA = {"사진", "동영상", "이모티콘", "파일", "음성메시지", "스티커", "음성", "미디어"}


@dataclass
class Message:
    time: str
    speaker: str
    text: str

    @property
    def is_media(self) -> bool:
        t = self.text.strip()
        if t.startswith("[") and t.endswith("]"):
            t = t[1:-1].strip()
        return not t or t in MEDIA or re.fullmatch(r"사진 \d+장", t) is not None


def _json_text(t: object) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return "".join(x if isinstance(x, str) else str(x.get("text", "")) for x in t)
    return "" if t is None else str(t)


def parse_json(text: str, limit: int | None = None) -> list[Message]:
    data = json.loads(text.lstrip("\ufeff"))
    items = data.get("messages", []) if isinstance(data, dict) else data
    msgs: list[Message] = []
    for m in items:
        if not isinstance(m, dict) or m.get("type", "message") != "message":
            continue
        speaker = m.get("from")
        body = _json_text(m.get("text"))
        if not speaker or not body.strip():
            continue
        msg = Message(str(m.get("date", "")).replace("T", " ")[:16], str(speaker), body)
        if msg.is_media:
            continue
        if limit and len(msgs) >= limit:
            break
        msgs.append(msg)
    return msgs


def load_chat(path: str, limit: int | None = None) -> list[Message]:
    with open(path, encoding="utf-8-sig") as f:
        return parse_json(f.read(), limit)


def speakers(msgs: list[Message]) -> list[str]:
    return [s for s, _ in Counter(m.speaker for m in msgs).most_common()]


def to_transcript(msgs: list[Message]) -> str:
    return "\n".join(f"{m.speaker}: {m.text}" for m in msgs)
