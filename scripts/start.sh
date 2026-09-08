#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo 'Đã tạo .env. Điền GEMINI_API_KEY và SOURCE_DIR rồi chạy lại.'
  exit 1
fi
if [ -f .active-image ]; then
  TALKCUT_IMAGE=$(cat .active-image)
  case "$TALKCUT_IMAGE" in talkcut-studio:v*) ;; *) echo 'Mốc phiên bản không hợp lệ.'; exit 1;; esac
  export TALKCUT_IMAGE
  docker compose up -d --no-build
else
  docker compose up -d --build
fi
echo 'TalkCut Studio: http://localhost:8092'
