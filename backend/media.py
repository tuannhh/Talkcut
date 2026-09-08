import json
import subprocess
from pathlib import Path
from .config import FFMPEG, FFPROBE, THREADS


class MediaError(RuntimeError):
    pass


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
    ffmpeg(['-ss', str(seconds), '-i', path, '-frames:v', '1', '-vf', 'scale=720:-2', dest], 120)
    return dest


def encode_args():
    return ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', THREADS, '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart']


def normalized_video(path, target):
    info = probe(path)
    args = ['-i', path]
    if not info['has_audio']:
        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    args += ['-map', '0:v:0', '-map', '0:a:0' if info['has_audio'] else '1:a:0', '-vf',
             'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1',
             '-t', str(info['duration']), *encode_args(), target]
    ffmpeg(args)
