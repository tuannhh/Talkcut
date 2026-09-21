#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo 'Đã tạo .env. Điền GEMINI_API_KEY và SOURCE_DIR rồi chạy lại.'
  exit 1
fi

# Auto-detect an NVIDIA GPU + the Docker NVIDIA Container Toolkit. Both the
# studio and face-engine images always carry GPU support (CUDA runtime libs,
# NVENC-capable ffmpeg) but stay pure-CPU unless the container actually gets
# GPU device access — compose.gpu.yaml is what grants that access, and
# Docker Compose has no way to request a device "if available", so this
# script decides for the user instead of asking them to remember a flag.
COMPOSE_FILES="-f compose.yaml"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1 \
   && docker info 2>/dev/null | grep -qi 'nvidia'; then
  COMPOSE_FILES="$COMPOSE_FILES -f compose.gpu.yaml"
  echo 'Đã phát hiện GPU NVIDIA — bật tăng tốc GPU (render + nhận diện khuôn mặt).'
else
  echo 'Không phát hiện GPU NVIDIA (hoặc thiếu NVIDIA Container Toolkit) — chạy CPU-only.'
fi

if [ -f .active-image ]; then
  TALKCUT_IMAGE=$(cat .active-image)
  case "$TALKCUT_IMAGE" in talkcut-studio:v*) ;; *) echo 'Mốc phiên bản không hợp lệ.'; exit 1;; esac
  export TALKCUT_IMAGE
  TALKCUT_FACE_IMAGE="talkcut-face-engine:${TALKCUT_IMAGE#talkcut-studio:}"
  export TALKCUT_FACE_IMAGE
  docker compose $COMPOSE_FILES up -d --no-build
else
  docker compose $COMPOSE_FILES up -d --build
fi
echo 'TalkCut Studio: http://localhost:8092'
