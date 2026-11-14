#!/usr/bin/env python3
"""터미널에서 실행하는 '내 말투 남자친구' 챗봇.

예) python main.py ~/Desktop/claude/Talk.txt                # 분석 후 대화
    python main.py Talk.txt --me 홍길동                       # 내 이름 지정
    python main.py --load output/Talk_홍길동                   # 저장된 style.md/memory.md로 바로 대화
"""
import argparse
import os
import sys

from boyfriend import analyze, config, default_out_dir, load_boyfriend, load_kakao, speakers
from boyfriend import llm


def pick_speaker(names: list[str]) -> str:
    print("대화 참여자:")
    for i, n in enumerate(names, 1):
        print(f"  {i}. {n}")
    while True:
        s = input("내 이름 번호를 고르세요> ").strip()
        if s.isdigit() and 1 <= int(s) <= len(names):
            return names[int(s) - 1]


def main():
    ap = argparse.ArgumentParser(description="카톡 대화로 내 말투+기억을 추출해 Qwen3.8 남자친구 만들기")
    ap.add_argument("talk", nargs="?", help="대화 파일 경로 (카카오톡 txt 또는 JSON)")
    ap.add_argument("--me", help="대화 속 내 이름 (생략 시 선택)")
    ap.add_argument("--limit", type=int, default=config.MAX_MESSAGES, help="앞에서부터 입력으로 쓸 메시지 수")
    ap.add_argument("--out", help="분석 결과 저장 폴더 (기본: output/<파일이름>_<내 이름>)")
    ap.add_argument("--load", help="저장된 분석 폴더로 바로 대화 (분석 생략)")
    ap.add_argument("--think", action="store_true", help="말투 분석 시 Qwen thinking 모드")
    a = ap.parse_args()
    if not a.talk and not a.load:
        ap.error("대화 파일 경로 또는 --load 가 필요합니다.")

    try:
        print(f"[vLLM] {config.VLLM_BASE_URL} → {llm.health()}")
    except Exception as e:
        sys.exit(f"vLLM 서버 연결 실패: {e}\nSSH 터널/VLLM_BASE_URL을 확인하세요.")

    if a.load:
        out = a.load
    else:
        msgs = load_kakao(a.talk, a.limit)
        names = speakers(msgs)
        if len(names) < 2:
            sys.exit("대화 참여자가 2명 이상이어야 합니다.")
        print(f"[파싱] 앞 {len(msgs)}개 메시지 ({msgs[0].time} ~ {msgs[-1].time})")
        me = a.me or pick_speaker(names)
        out = analyze(msgs, me, a.out or default_out_dir(a.talk, me), think=a.think)

    for name in ("style.md", "memory.md"):
        print("\n" + open(os.path.join(out, name), encoding="utf-8").read())

    bf = load_boyfriend(out)
    print(f"=== {bf.me}(남자친구)와 대화 시작 ===  /reset 초기화, /exit 종료\n")
    while True:
        try:
            u = input(f"{bf.partner}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not u:
            continue
        if u == "/exit":
            break
        if u == "/reset":
            bf.reset()
            print("(대화 초기화)")
            continue
        res, lines = bf.reply(u)
        if res.emergency:
            print(f"\n  🚨 [비상 알림 → {bf.me}] 심각도 {res.severity}: {res.emergency_reason}\n")
        for line in lines:
            print(f"  {bf.me}: {line}")
        if bf.pending:
            print(f"\n  ❓ [주인 확인 필요 → {bf.me}] {bf.pending['question']}")
            ans = input(f"  {bf.me}(주인) 답변 (Enter=나중에)> ").strip()
            if ans:
                out = ""
                for out in bf.answer_owner_stream(ans):
                    pass
                for line in out.splitlines():
                    print(f"  {bf.me}: {line}")
                print("  (memory.md에 저장됨)")
            print()


if __name__ == "__main__":
    main()
