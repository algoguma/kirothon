# ruff: noqa: E501  (Korean prompt text)
"""Extract shared memories (plans, events, facts) from past chat.

Ported from prototype/boyfriend/memory.py: split into chunks, extract in parallel, then merge.
"""

import json
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .parser import Message
from .style import parse_json

MEMORY_CHUNK = 250

SCHEMA = """{{
  "plans": [{{"what": "약속/계획 내용 (누구와, 어디서, 무엇을)", "when": "언제 (대화에 나온 표현 그대로 + 실제 날짜 추정)", "status": "예정/완료/취소/미정", "detail": "시간, 장소, 준비물 등 구체 정보"}}],
  "events": [{{"date": "날짜", "what": "있었던 일"}}],
  "partner_facts": ["{partner}에 대한 사실 (일, 취향, 가족, 감정 상태 등)"],
  "my_facts": ["{me}에 대한 사실"],
  "people": [{{"name": "이름", "relation": "관계/설명"}}],
  "places": ["언급된 장소, 식당, 여행지와 맥락"],
  "inside_jokes": ["둘만의 농담, 별명, 반복되는 소재"],
  "unresolved": ["답을 안 했거나 나중에 하기로 한 얘기"]
}}"""

CHUNK_PROMPT = """아래는 "{me}"와 "{partner}"의 대화 일부야. (각 줄 앞의 [날짜 시간] 참고)
나중에 {me}가 이 내용을 기억하고 대화를 이어갈 수 있도록, 기억해야 할 정보를 빠짐없이 뽑아 JSON으로 출력해.
- 약속/계획(식당, 여행, 만남, 할 일)은 사소해도 전부 넣고, 시간/장소/누구와를 구체적으로 적어.
- "내일", "주말" 같은 표현은 대화 날짜 기준으로 실제 날짜도 같이 적어.
- 대화에 없는 내용은 지어내지 마. 해당 없는 항목은 빈 배열.

출력 형식:
{schema}

[대화]
{transcript}
"""

MERGE_PROMPT = """아래는 "{me}"와 "{partner}"의 긴 대화를 구간별로 나눠 뽑은 기억 JSON 목록이야 (시간순).
하나의 JSON으로 합쳐줘.
- 중복은 합치고, 같은 계획이 나중에 바뀌었으면 최신 내용으로 반영하고 status도 갱신해.
- 약속/계획과 구체 정보(시간, 장소)는 절대 빠뜨리지 마.
- 대화에 없는 내용은 지어내지 마.

출력 형식:
{schema}

[구간별 기억]
{chunks}
"""


def _transcript_with_time(msgs: list[Message]) -> str:
    return "\n".join(f"[{m.time}] {m.speaker}: {m.text}" for m in msgs)


def _extract_chunk(msgs: list[Message], me: str, partner: str) -> dict:
    prompt = CHUNK_PROMPT.format(
        me=me,
        partner=partner,
        schema=SCHEMA.format(me=me, partner=partner),
        transcript=_transcript_with_time(msgs),
    )
    raw = llm.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=3000,
        json_mode=True,
        long=True,
    )
    try:
        return parse_json(raw)
    except ValueError:
        return {}


def extract_memory(msgs: list[Message], me: str, partner: str) -> dict:
    chunks = [msgs[i : i + MEMORY_CHUNK] for i in range(0, len(msgs), MEMORY_CHUNK)]
    with ThreadPoolExecutor(max_workers=len(chunks) or 1) as ex:  # vLLM batches them
        parts = list(ex.map(lambda c: _extract_chunk(c, me, partner), chunks))

    if len(parts) <= 1:
        memory = parts[0] if parts else {}
    else:
        joined = "\n\n".join(
            f"## 구간 {i + 1} ({c[0].time} ~ {c[-1].time})\n{json.dumps(p, ensure_ascii=False)}"
            for i, (c, p) in enumerate(zip(chunks, parts, strict=True))
        )
        prompt = MERGE_PROMPT.format(
            me=me, partner=partner, schema=SCHEMA.format(me=me, partner=partner), chunks=joined
        )
        raw = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000,
            json_mode=True,
            long=True,
        )
        try:
            memory = parse_json(raw)
        except ValueError:  # merge failed: concatenate the chunk results
            memory = {}
            for p in parts:
                for k, v in p.items():
                    memory.setdefault(k, []).extend(v if isinstance(v, list) else [v])

    memory["_range"] = f"{msgs[0].time} ~ {msgs[-1].time}" if msgs else ""
    memory["_count"] = len(msgs)
    return memory


def memory_to_markdown(mem: dict, me: str, partner: str) -> str:
    def fmt(x: object) -> str:
        if isinstance(x, dict):
            return " · ".join(f"{v}" for v in x.values() if v)
        return str(x)

    sections = [
        ("plans", "약속 / 계획"),
        ("events", "있었던 일"),
        ("partner_facts", f"{partner}에 대해"),
        ("my_facts", f"{me}에 대해"),
        ("people", "등장인물"),
        ("places", "장소"),
        ("inside_jokes", "둘만의 농담 / 소재"),
        ("unresolved", "나중에 하기로 한 얘기"),
    ]
    out = [
        f"# 기억 노트: {me} ↔ {partner}",
        f"> 과거 대화 {mem.get('_count', '?')}개 ({mem.get('_range', '')})에서 추출",
        "",
    ]
    for key, title in sections:
        items = mem.get(key) or []
        if not items:
            continue
        out.append(f"## {title}")
        if key == "plans":
            for p in items:
                if isinstance(p, dict):
                    status = f"[{p.get('status', '')}] " if p.get("status") else ""
                    when = f" — {p['when']}" if p.get("when") else ""
                    detail = f" ({p['detail']})" if p.get("detail") else ""
                    out.append(f"- {status}{p.get('what', '')}{when}{detail}")
                else:
                    out.append(f"- {p}")
        else:
            out += [f"- {fmt(i)}" for i in items]
        out.append("")
    return "\n".join(out).strip() + "\n"
