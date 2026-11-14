#!/usr/bin/env python3
"""해커톤 실행 파일: 대화 파일(txt/JSON) + 내 이름 + 상대 메시지 → JSON (답변, 비상, 확인필요)

사용법
  # 메시지 1개 → JSON 객체 1개
  python run.py --talk Talk.txt --me 홍길동 --message "오빠 뭐해??"

  # 메시지 여러 개 (대화가 이어짐) → JSON 배열
  python run.py --talk Talk.txt --me 홍길동 -m "오빠 뭐해??" -m "나 목 아파ㅜㅜ"

  # 표준입력: 한 줄에 메시지 1개 → 한 줄에 JSON 1개 (JSONL). 켜져 있는 동안 대화를 기억/참조, /reset 으로 초기화
  echo "오빠 뭐해??" | python run.py --talk Talk.txt --me 홍길동

- 처음 실행 시 Qwen3.8이 말투/기억을 분석해 output/<파일>_<내이름>/에 저장 (약 2분), 이후에는 바로 불러옴
- stdout에는 JSON만 출력, 진행 로그는 stderr
"""
import argparse
import json
import sys

from boyfriend import analyze, config, default_out_dir, has_saved, load_boyfriend, load_kakao, speakers
from boyfriend import llm


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def respond(bf, message: str) -> dict:
    """메시지 1개 처리 → 결과 dict"""
    check, lines = bf.reply(message)
    pending = bf.pending  # reply() 안에서 확인 필요 시 설정됨
    result = {
        "turn": len([h for h in bf.history if h["role"] == "user"]),  # 이번 대화에서 몇 번째 메시지인지
        "input": message,
        "reply": "\n".join(lines),
        "reply_lines": lines,                       # 카톡 말풍선 단위
        "emergency": {
            "is_emergency": check.emergency,
            "severity": check.severity if check.emergency else "",   # 낮음 / 중간 / 높음
            "reason": check.emergency_reason if check.emergency else "",
        },
        "needs_confirmation": {
            "is_needed": bool(pending),
            "question": pending["question"] if pending else "",       # 나(주인)에게 물어볼 질문
        },
    }
    bf.pending = None  # 실행 파일에서는 주인 답변을 받지 않으므로 다음 메시지로 넘어감
    return result


def build(args):
    msgs = load_kakao(args.talk, args.limit)
    names = speakers(msgs)
    if args.me not in names:
        raise ValueError(f"'{args.me}'가 대화에 없습니다. 참여자: {names}")
    out = default_out_dir(args.talk, args.me)
    if has_saved(out) and not args.reanalyze:
        log(f"[불러오기] {out}")
    else:
        log(f"[분석] 앞 {len(msgs)}개 메시지로 말투/기억 분석 중 (약 2분)...")
        analyze(msgs, args.me, out, log=log)
    return load_boyfriend(out)


def main():
    ap = argparse.ArgumentParser(description="대화 txt + 내 이름 + 상대 메시지 → JSON(답변, 비상, 확인필요)")
    ap.add_argument("--talk", required=True, help="대화 파일 경로 (카카오톡 txt 또는 JSON)")
    ap.add_argument("--me", required=True, help="대화 속 내 이름 (이 사람 말투로 답변)")
    ap.add_argument("-m", "--message", action="append", help="상대가 보낸 메시지 (여러 번 지정 가능, 생략 시 표준입력)")
    ap.add_argument("--limit", type=int, default=config.MAX_MESSAGES, help="앞에서부터 사용할 메시지 수")
    ap.add_argument("--reanalyze", action="store_true", help="저장된 분석 무시하고 새로 분석")
    ap.add_argument("--pretty", action="store_true", help="JSON 들여쓰기")
    args = ap.parse_args()
    indent = 2 if args.pretty else None

    def emit(obj):
        print(json.dumps(obj, ensure_ascii=False, indent=indent), flush=True)

    try:
        llm.health()
        bf = build(args)
    except Exception as e:
        emit({"error": f"{type(e).__name__}: {e}"})
        sys.exit(1)

    if args.message:  # 인자로 받은 메시지
        results = [respond(bf, m) for m in args.message]
        emit(results[0] if len(results) == 1 else results)
    else:  # 표준입력 JSONL 모드: 프로세스가 켜져 있는 동안 대화를 기억하고 참조 (최근 30턴)
        if sys.stdin.isatty():
            log("상대 메시지를 한 줄씩 입력하세요. 대화는 계속 이어집니다. (/reset 초기화, Ctrl+D 종료)")
        for line in read_lines():
            msg = line.strip()
            if not msg:
                continue
            if msg == "/reset":
                bf.reset()
                emit({"reset": True})
                continue
            try:
                emit(respond(bf, msg))
            except Exception as e:
                emit({"input": msg, "error": f"{type(e).__name__}: {e}"})


def read_lines():
    """입력 줄 읽기.
    - 터미널 직접 입력: readline(input)으로 읽어 한글 지우기/수정이 깨지지 않게 함
      (sys.stdin 직접 읽기는 터미널이 한글을 바이트 단위로 지워 글자가 빠질 수 있음)
    - 파이프/파일 입력: 그대로 한 줄씩
    """
    if not sys.stdin.isatty():
        yield from sys.stdin
        return
    try:
        import readline  # noqa: F401  (input()에 줄 편집 기능 활성화)
    except ImportError:
        pass
    while True:
        try:
            yield input()
        except EOFError:
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # Ctrl+C → 조용히 종료
        log("\n종료")
        sys.exit(130)
