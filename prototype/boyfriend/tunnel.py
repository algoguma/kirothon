"""vLLM 서버로 가는 SSH 터널 자동 연결.

.env 예)
  SSH_TUNNEL=user@server-ip        # 설정하면 자동 터널 사용
  SSH_KEY=~/.ssh/kirothon          # (선택) 키 파일
  SSH_PASSWORD=...                 # (선택) 비밀번호. 키도 비밀번호도 없으면 ssh가 터미널에서 물어봄
  SSH_PORT=22                      # (선택)
  SSH_REMOTE_PORT=8000             # (선택) 서버에서 vLLM이 듣는 포트

동작: VLLM_BASE_URL(localhost:포트)이 이미 열려 있으면 그대로 사용하고,
      아니면 `ssh -N -L 포트:localhost:SSH_REMOTE_PORT SSH_TUNNEL`을 백그라운드로 열고,
      프로그램이 끝나면 닫습니다.
"""
from __future__ import annotations

import atexit
import os
import shlex
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

from . import config

_proc: subprocess.Popen | None = None


def _log(*a):
    print(*a, file=sys.stderr, flush=True)  # stdout(JSON)을 더럽히지 않게 stderr로


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _close():
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(3)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


def ensure() -> None:
    """필요하면 SSH 터널을 열어 VLLM_BASE_URL에 접속 가능하게 만듦"""
    global _proc
    url = urlparse(config.VLLM_BASE_URL)
    host, port = url.hostname or "localhost", url.port or 80
    target = os.getenv("SSH_TUNNEL", "").strip()

    if _port_open(host, port):
        return  # 이미 연결됨 (터널을 직접 열었거나 서버에 바로 접속 가능)
    if not target:
        return  # 자동 터널 미사용 → 이후 연결 오류로 안내
    if host not in ("localhost", "127.0.0.1"):
        raise RuntimeError(f"SSH 자동 터널은 VLLM_BASE_URL이 localhost일 때만 씁니다 (현재 {host})")

    remote_port = os.getenv("SSH_REMOTE_PORT", "8000")
    cmd = ["ssh", "-N",
           "-L", f"{port}:localhost:{remote_port}",
           "-o", "ExitOnForwardFailure=yes",
           "-o", "ServerAliveInterval=30",
           "-o", "StrictHostKeyChecking=accept-new"]
    if os.getenv("SSH_PORT"):
        cmd += ["-p", os.getenv("SSH_PORT")]
    key = os.path.expanduser(os.getenv("SSH_KEY", "").strip())
    if key:
        cmd += ["-i", key, "-o", "BatchMode=yes"]  # 키 사용 시 비밀번호 프롬프트 없이
    cmd.append(target)

    env = os.environ.copy()
    password = os.getenv("SSH_PASSWORD", "")
    if password and not key:
        # .env의 SSH_PASSWORD를 ssh 내장 SSH_ASKPASS로 전달 (sshpass 등 추가 설치 불필요, 명령어/로그에 비밀번호 노출 없음)
        env.update(SSH_ASKPASS=os.path.join(os.path.dirname(__file__), "askpass.sh"),
                   SSH_ASKPASS_REQUIRE="force", DISPLAY=env.get("DISPLAY", ":0"))
        cmd[1:1] = ["-o", "PreferredAuthentications=password,keyboard-interactive",
                    "-o", "NumberOfPasswordPrompts=1"]

    _log(f"[터널] {' '.join(shlex.quote(c) for c in cmd)}")
    if not key and not password:
        _log("[터널] SSH 비밀번호를 입력하세요 (.env에 SSH_KEY 또는 SSH_PASSWORD를 넣으면 생략됩니다)")
    # stdin을 넘기지 않음: 비밀번호는 ssh가 터미널(/dev/tty)에서 직접 받고, 표준입력 모드의 메시지와 섞이지 않음
    _proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True, env=env, start_new_session=False)
    atexit.register(_close)

    deadline = time.time() + (20 if key else 90)  # 비밀번호 입력 시간 고려
    while time.time() < deadline:
        if _port_open(host, port):
            _log(f"[터널] 연결됨: localhost:{port} → {target}:{remote_port}")
            return
        if _proc.poll() is not None:  # ssh가 종료됨 = 실패
            err = (_proc.stderr.read() or "").strip().splitlines()
            _proc = None
            raise RuntimeError("SSH 터널 실패: " + (err[-1] if err else "원인 불명"))
        time.sleep(0.3)
    _close()
    raise RuntimeError("SSH 터널 연결 시간 초과")
