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
