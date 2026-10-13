import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
for directory in ('sources', 'assets', 'renders', 'jobs'):
    (DATA / directory).mkdir(exist_ok=True)
SOURCE_ROOT = Path(os.getenv('SOURCE_ROOT', '/sources')).resolve()
API_KEY = os.getenv('GEMINI_API_KEY', '')
CONTENT_MODEL = os.getenv('GEMINI_CONTENT_MODEL', 'gemini-3.8-flash')
STT_MODEL = os.getenv('GEMINI_STT_MODEL', 'gemini-3.5-transcribe')
TTS_MODEL = os.getenv('GEMINI_TTS_MODEL', 'gemini-3.1-flash-tts-preview')
FFMPEG = os.getenv('FFMPEG', 'ffmpeg')
FFPROBE = os.getenv('FFPROBE', 'ffprobe')
THREADS = str(max(1, min(16, int(os.getenv('RENDER_THREADS', '4')))))
MAX_BYTES = int(float(os.getenv('MAX_UPLOAD_GB', '10')) * 1024 ** 3)
# libx264 preset for exports. Measured on 60 s of 1080x1920 output at crf 18:
# veryfast encodes 2-2.7x faster than fast with SSIM 0.99 against it and a
# smaller file, so a CPU-only server should use veryfast.
X264_PRESETS = ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow')
RENDER_PRESET = os.getenv('RENDER_PRESET', 'fast').lower()
if RENDER_PRESET not in X264_PRESETS:
    RENDER_PRESET = 'fast'

# Optional NVIDIA acceleration for ffmpeg (NVENC encode / CUDA decode).
# auto: use it when a GPU + capable ffmpeg are both detected; cuda: force on
# (fails loudly if unavailable); cpu: force the original libx264 path.
RENDER_ACCEL = os.getenv('RENDER_ACCEL', 'auto').lower()

# Google STT requests are network-bound: several five-minute chunks of a long
# talk run at once (each chunk is cached, so a retry only redoes missing ones).
STT_PARALLEL = max(1, min(8, int(os.getenv('STT_PARALLEL', '4'))))

# Shared server edition: accounts issued by an administrator. Off for the
# personal desktop install. Origins allowed to send writes besides the page's
# own host (comma separated, e.g. https://talkcut.misa.local).
AUTH_ENABLED = os.getenv('TALKCUT_AUTH', 'off').lower() in ('1', 'on', 'true', 'yes')
ALLOWED_ORIGINS = {o.strip().rstrip('/') for o in os.getenv('TALKCUT_ALLOWED_ORIGINS', '').split(',') if o.strip()}
# auto: Secure cookie when the request arrived over HTTPS (X-Forwarded-Proto from the proxy).
COOKIE_SECURE = os.getenv('TALKCUT_COOKIE_SECURE', 'auto').lower()

# Worker threads per job lane (see pipeline.LANES). Rendering and face framing
# are CPU heavy: raise them only on a server with spare cores and memory.
LANE_WORKERS = {lane: max(1, min(8, int(os.getenv(f'{lane.upper()}_WORKERS', '1')))) for lane in ('render', 'framing', 'ingest', 'ai')}
# After AI suggests clips, prepare the framing of the best N in the background
# so they open ready (0 = only when someone opens a clip).
PREPARE_FRAMING_TOP = max(0, min(50, int(os.getenv('PREPARE_FRAMING_TOP', '0'))))
# Light H.264 preview for sources the office browsers decode poorly (4K, AV1,
# HEVC...): auto = only for those, off = always play the original.
PREVIEW_PROXY = os.getenv('PREVIEW_PROXY', 'off').lower()
