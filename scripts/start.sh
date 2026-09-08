#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo 'Đã tạo .env. Điền GEMINI_API_KEY và SOURCE_DIR rồi chạy lại.'
  exit 1
fi
docker compose up -d --build
echo 'TalkCut Studio: http://localhost:8092'
