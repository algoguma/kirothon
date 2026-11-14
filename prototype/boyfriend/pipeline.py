"""전체 흐름: 대화 1000개 → (최근 500개로 말투 분석 ‖ 1000개 전체로 기억 추출) → md 저장 → 남자친구

저장 결과 (output/<대화파일이름>_<내 이름>/)
- style.md   : 말투 프로필  (사람이 읽고 고칠 수 있음, 그대로 프롬프트에 들어감)
- memory.md  : 기억 노트    (약속/계획/사건/상대 정보)
- session.json : 이름, 최근 대화 원문 등 복원용 정보
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from . import config
from .memory import extract_memory, memory_to_markdown
from .parser import Message, speakers
from .persona import Boyfriend
from .style import extract_style, style_to_markdown


def analyze(msgs: list[Message], me: str, out_dir: str | None = None,
            think: bool = False, log=print) -> str:
    """말투 분석 + 기억 추출을 Qwen3.8로 동시에 실행하고 out_dir에 저장. out_dir 경로 반환."""
    names = speakers(msgs)
    if me not in names:
        raise ValueError(f"'{me}'가 대화에 없습니다. 참여자: {names}")
    partner = next(n for n in names if n != me)
    style_msgs = msgs[-config.STYLE_MESSAGES:]

    log(f"[분석] 말투: 최근 {len(style_msgs)}개 / 기억: 전체 {len(msgs)}개 "
        f"({config.MEMORY_CHUNK}개씩 {-(-len(msgs) // config.MEMORY_CHUNK)}구간) — Qwen3.8 병렬 호출")
    with ThreadPoolExecutor(2) as ex:
        f_style = ex.submit(extract_style, style_msgs, me, partner, think)
        f_mem = ex.submit(extract_memory, msgs, me, partner)
        style, memory = f_style.result(), f_mem.result()

    out_dir = out_dir or os.path.join(config.OUTPUT_DIR, "session")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "style.md"), "w", encoding="utf-8") as f:
        f.write(style_to_markdown(style))
    with open(os.path.join(out_dir, "memory.md"), "w", encoding="utf-8") as f:
        f.write(memory_to_markdown(memory, me, partner))
    recent = msgs[-config.RECENT_RAW:]
    with open(os.path.join(out_dir, "session.json"), "w", encoding="utf-8") as f:
        json.dump({"me": me, "partner": partner, "style": style, "memory": memory,
                   "recent": [asdict(m) for m in recent]}, f, ensure_ascii=False, indent=2)
    log(f"[저장] {out_dir}/style.md, memory.md")
    return out_dir


def load_boyfriend(out_dir: str) -> Boyfriend:
    """저장된 style.md / memory.md로 남자친구 생성 (md를 직접 고쳤다면 고친 내용이 반영됨)"""
    with open(os.path.join(out_dir, "session.json"), encoding="utf-8") as f:
        s = json.load(f)
    with open(os.path.join(out_dir, "style.md"), encoding="utf-8") as f:
        style_md = f.read()
    with open(os.path.join(out_dir, "memory.md"), encoding="utf-8") as f:
        memory_md = f.read()
    recent = [Message(**m) for m in s["recent"]]
    return Boyfriend(s["me"], s["partner"], style_md, memory_md, recent, out_dir=out_dir)


def default_out_dir(talk_path: str, me: str) -> str:
    """분석 저장 폴더: output/<대화파일이름>_<내 이름>  (같은 대화도 누구 기준인지에 따라 따로 저장)"""
    stem, ext = os.path.splitext(os.path.basename(talk_path))
    if ext.lower() not in ("", ".txt"):  # Talk.txt / Talk.json처럼 이름이 같은 다른 파일과 섞이지 않게
        stem += "_" + ext.lstrip(".").lower()
    safe_me = re.sub(r"[^\w]", "", me) or "me"   # 이모지/기호 제거
    return os.path.join(config.OUTPUT_DIR, f"{stem}_{safe_me}")


def has_saved(out_dir: str) -> bool:
    return all(os.path.exists(os.path.join(out_dir, n)) for n in ("session.json", "style.md", "memory.md"))
