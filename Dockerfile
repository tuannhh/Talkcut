FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fontconfig ca-certificates libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY backend/fonts /usr/local/share/fonts/talkcut
RUN fc-cache -f
COPY --from=frontend /build/dist ./frontend/dist
RUN useradd -m -u 10001 studio && mkdir /data && chown studio:studio /data
USER studio
ENV DATA_DIR=/data SOURCE_ROOT=/sources PYTHONUNBUFFERED=1
EXPOSE 8092
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8092/api/health')"
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8092", "--workers", "1"]
