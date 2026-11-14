#!/bin/bash
# 원격 GPU 서버에서 실행: Qwen3.8-27B를 vLLM OpenAI 호환 API로 서빙
# (A100 80GB x2, BF16, localhost:8000 — 로컬에서는 SSH 터널로 접속)
# 드라이버가 CUDA 12.8이면 cu129 빌드 vLLM(예: 0.31.0) 사용
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-2,3}
exec vllm serve Qwen/Qwen3.8-27B \
  --served-model-name qwen3.8-27b \
  --host 127.0.0.1 --port 8000 \
  --tensor-parallel-size 2 \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.90 \
  --reasoning-parser qwen3 \
  --enable-prefix-caching
