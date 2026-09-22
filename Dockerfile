FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ffmpeg is built from source instead of `apt install ffmpeg` because Debian's
# packaged ffmpeg doesn't ship h264_nvenc. NVENC/NVDEC only need the header
# (nv-codec-headers) at build time — the actual encoder library
# (libnvidia-encode.so) comes from the host's NVIDIA driver at *runtime*, via
# the NVIDIA Container Toolkit, so this stays a small, CUDA-toolkit-free
# build and produces one binary that works with or without a GPU: without
# --gpus/NVIDIA_DRIVER_CAPABILITIES=video, h264_nvenc simply fails to load
# and backend/media.py's `_accel_enabled()` falls back to libx264 (also
# compiled in), same as always. An older nv-codec-headers tag is pinned
# deliberately: a newer one silently raises the *minimum required NVIDIA
# driver version* for NVENC (confirmed on real hardware: a prebuilt static
# ffmpeg needed driver >=610; this build only needs >=530.41).
FROM debian:bookworm-slim AS ffmpeg-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential yasm nasm pkg-config libx264-dev libass-dev libmp3lame-dev libdav1d-dev zlib1g-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN git clone --depth 1 --branch n12.1.14.0 https://github.com/FFmpeg/nv-codec-headers.git \
    && make -C nv-codec-headers install
RUN git clone --depth 1 --branch n7.1 https://github.com/FFmpeg/FFmpeg.git ffmpeg
WORKDIR /build/ffmpeg
# --enable-libass: karaoke captions (`ass=` filter, caption_enabled defaults
# to true). --enable-zlib: PNG decode — watermark/intro art is rendered to
# PNG by Pillow then composited with `overlay`, which needs to decode that
# PNG even for the plain-text watermark default. --enable-libmp3lame: MP3
# audio encode — the analyze pipeline extracts audio-*.mp3 for Google STT
# (pipeline.py). Debian's packaged ffmpeg shipped this; the from-source
# build must enable it explicitly or `analyze` fails with "Encoder not found".
# --enable-libdav1d: *software* AV1 decode. FFmpeg's built-in `av1` decoder is
# hwaccel-only (no software path), so without dav1d an AV1 source decodes only
# on a GPU (av1_cuvid). That silently breaks the CPU-only path this single
# image promises — AV1 phone/screen recordings fail with "Your platform doesn't
# support hardware accelerated AV1 decoding". Debian's packaged ffmpeg shipped
# dav1d; the from-source build must enable it or CPU render of AV1 dies.
RUN ./configure --enable-gpl --enable-nonfree --enable-cuda --enable-cuvid --enable-nvenc --enable-libx264 --enable-libass --enable-libmp3lame --enable-libdav1d --enable-zlib \
      --disable-doc --disable-debug --disable-ffplay \
    && make -j"$(nproc)" \
    && make install DESTDIR=/build/out

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core fontconfig ca-certificates libglib2.0-0 libgl1 libx264-164 libass9 libmp3lame0 libdav1d6 zlib1g && rm -rf /var/lib/apt/lists/*
COPY --from=ffmpeg-build /build/out/usr/local/bin/ffmpeg /build/out/usr/local/bin/ffprobe /usr/local/bin/
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
ENV DATA_DIR=/data SOURCE_ROOT=/sources PYTHONUNBUFFERED=1 RENDER_ACCEL=auto
EXPOSE 8092
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8092/api/health')"
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8092", "--workers", "1"]
