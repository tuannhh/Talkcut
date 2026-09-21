import json
import subprocess
from pathlib import Path
from .config import FFMPEG, FFPROBE, THREADS, RENDER_ACCEL
from . import gpu_profile


class MediaError(RuntimeError):
    pass


def _resolved_render_accel():
    from . import accel_settings
    return accel_settings.get().get('render_accel', RENDER_ACCEL)


def _accel_enabled():
    mode = _resolved_render_accel()
    if mode == 'cpu':
        return False
    gpu = gpu_profile.detect_gpu()
    if mode == 'cuda':
        return True  # forced: let ffmpeg fail loudly if the hardware/driver isn't there
    return bool(gpu)  # auto: only when a GPU is actually present


def hwaccel_input_args():
    """Args to place immediately before `-i <source>` to decode via NVDEC.

    Safe no-op when acceleration is off or ffmpeg lacks the `cuda` hwaccel;
    frames still come back as normal CPU frames for the existing filters.
    """
    if not _accel_enabled() or not gpu_profile.ffmpeg_capabilities()['cuda_decode']:
        return []
    return ['-hwaccel', 'cuda']


def run(args, timeout=7200):
    try:
        p = subprocess.run([str(x) for x in args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MediaError('Xử lý quá thời gian cho phép. Thử một nguồn ngắn hơn.') from None
    if p.returncode:
        raise MediaError(p.stderr.decode(errors='replace')[-1800:])
    return p.stdout


def ffmpeg(args, timeout=7200):
    return run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-threads', THREADS, '-filter_complex_threads', '1', *args], timeout)


def ffmpeg_progress(args, duration, on_frac, timeout=7200):
    """Like ffmpeg() but streams real encode progress via `-progress pipe:1`.

    `on_frac` is called with a 0..1 fraction as ffmpeg advances through
    `duration` seconds of output. Errors behave exactly like run(): a non-zero
    exit raises MediaError with the stderr tail. Progress reporting is
    best-effort — any hiccup reading the pipe just means a coarser bar, never
    a failed or hung render.
    """
    import threading
    full = [str(x) for x in [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-threads', THREADS,
                             '-filter_complex_threads', '1', '-progress', 'pipe:1', '-nostats', *args]]
    try:
        proc = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as error:
        raise MediaError(str(error)) from None
    stderr_chunks = []
    stderr_thread = threading.Thread(target=lambda: stderr_chunks.append(proc.stderr.read()), daemon=True)
    stderr_thread.start()
    try:
        for line in proc.stdout:
            if duration and line.startswith('out_time_us='):
                try:
                    micros = int(line.split('=', 1)[1])
                    on_frac(max(0, min(1, micros / 1_000_000 / duration)))
                except (ValueError, ZeroDivisionError):
                    pass
    finally:
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise MediaError('Xử lý quá thời gian cho phép. Thử một nguồn ngắn hơn.') from None
        stderr_thread.join(timeout=5)
    if proc.returncode:
        raise MediaError((stderr_chunks[0] if stderr_chunks else '')[-1800:] or 'ffmpeg thất bại.')
    on_frac(1)


def probe(path):
    data = json.loads(run([FFPROBE, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path], 60))
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
    result = {'duration': float(data.get('format', {}).get('duration', 0)), 'has_audio': bool(audio)}
    if video:
        w, h = video['width'], video['height']
        rotation = next((s.get('rotation', 0) for s in video.get('side_data_list', []) if 'rotation' in s), 0)
        if abs(rotation) % 180 == 90:
            w, h = h, w
        result.update(width=w, height=h, codec=video['codec_name'])
    return result


def frame(path, dest, seconds=0):
    ffmpeg(['-ss', str(seconds), *hwaccel_input_args(), '-i', path, '-frames:v', '1', '-vf', 'scale=720:-2', dest], 120)
    return dest


def encode_args():
    if _accel_enabled() and gpu_profile.ffmpeg_capabilities()['nvenc']:
        # NVENC has no direct CRF equivalent, and is measurably less bit-efficient
        # than libx264 at the same visual quality (measured on real 1080x1920
        # output: uncapped '-cq 19 -b:v 0' produced an 85% larger file than the
        # libx264 crf-18 output at the same duration/resolution for no visible
        # quality gain). cq 23 plus a bitrate cap brings size back in line with
        # the CPU path while keeping NVENC's real advantage, which is speed.
        return ['-c:v', 'h264_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '23',
                '-b:v', '6M', '-maxrate', '9M', '-bufsize', '12M',
                '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart']
    return ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', THREADS, '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart']


def normalized_video(path, target):
    info = probe(path)
    args = [*hwaccel_input_args(), '-i', path]
    if not info['has_audio']:
        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    args += ['-map', '0:v:0', '-map', '0:a:0' if info['has_audio'] else '1:a:0', '-vf',
             'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1',
             '-t', str(info['duration']), *encode_args(), target]
    ffmpeg(args)
