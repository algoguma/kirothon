#!/bin/bash
# 실행 래퍼: 프로젝트 가상환경(.venv)이 있으면 그걸로, 없으면 시스템 python3로 run.py 실행
# 예) ./run.sh --talk Talk.txt --me 홍길동 --message "오빠 뭐해??"
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY=python3
exec "$PY" "$DIR/run.py" "$@"
