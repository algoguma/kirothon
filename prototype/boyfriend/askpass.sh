#!/bin/sh
# ssh가 비밀번호를 물을 때 호출됨 → .env의 SSH_PASSWORD를 전달 (tunnel.py에서 사용)
printf '%s\n' "$SSH_PASSWORD"
