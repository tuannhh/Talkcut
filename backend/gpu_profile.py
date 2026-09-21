"""GPU/VRAM detection for optional CUDA-accelerated render.

Fully opt-in: every function here degrades to "no GPU" when nvidia-smi or
NVENC/NVDEC-capable ffmpeg is absent, so a CPU-only machine behaves exactly
like before. Results are memoized per-process since hardware doesn't change
while the container runs.
"""
import re
import subprocess
from functools import lru_cache

from .config import FFMPEG


@lru_cache(maxsize=1)
def detect_gpu():
    """Return {'name': str, 'vram_mb': int} for the first NVIDIA GPU, or None."""
    try:
        out = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, timeout=10, text=True,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode or not out.stdout.strip():
        return None
    first = out.stdout.strip().splitlines()[0]
    match = re.match(r'\s*(.+?)\s*,\s*(\d+)\s*$', first)
    if not match:
        return None
    return {'name': match.group(1), 'vram_mb': int(match.group(2))}


@lru_cache(maxsize=1)
def ffmpeg_capabilities():
    """Return {'nvenc': bool, 'cuda_decode': bool} for the ffmpeg binary in use."""
    caps = {'nvenc': False, 'cuda_decode': False}
    try:
        encoders = subprocess.run([FFMPEG, '-hide_banner', '-encoders'], capture_output=True, timeout=10, text=True)
        caps['nvenc'] = 'h264_nvenc' in encoders.stdout
        hwaccels = subprocess.run([FFMPEG, '-hide_banner', '-hwaccels'], capture_output=True, timeout=10, text=True)
        caps['cuda_decode'] = 'cuda' in hwaccels.stdout
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return caps


def tier_for(vram_mb):
    """Round detected VRAM down to the nearest supported tier (MB), or None."""
    if vram_mb is None:
        return None
    for tier in (8192, 6144, 4096, 2048):
        if vram_mb >= tier * 0.9:  # allow for OS/driver reserved VRAM
            return tier
    return None
