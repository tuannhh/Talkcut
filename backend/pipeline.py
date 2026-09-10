import json
import math
import os
import queue
import shutil
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from . import config, store, google_ai, editor
from .media import ffmpeg, probe, frame
from .schemas import Settings, Word

jobs = queue.Queue()
submit_lock = threading.Lock()

# A landscape 1080p source only has about 608 pixels across a 9:16 crop.  It
# must then be enlarged to 1080px for the final video, which is visibly soft.
# Prefer a 2160p MP4 stream when YouTube offers it, while retaining sensible
# lower-resolution fallbacks for ordinary public videos.
YOUTUBE_FORMAT = 'bv*[height<=2160][ext=mp4]+ba[ext=m4a]/bv*[height<=2160]+ba/b[height<=2160]'


def enqueue(kind, target, payload=None):
    with submit_lock:
        active = next((j for j in store.listing('job') if j['kind'] == kind and j['target'] == target and j['status'] in ('queued', 'running')), None)
        if active:
            return active
        item = store.create('job', {'kind': kind, 'target': target, 'payload': payload or {}, 'status': 'queued', 'progress': 0, 'message': 'Đang chờ xử lý', 'error': None})
        jobs.put(item['id'])
        return item


def youtube_url(value):
    p = urlparse(value)
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Hãy nhập link HTTPS của YouTube.')
    if p.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        id = parse_qs(p.query).get('v', [''])[0] if p.path == '/watch' else p.path.split('/')[-1] if p.path.startswith(('/shorts/', '/live/')) else ''
    elif p.hostname == 'youtu.be':
        id = p.path.strip('/')
    else:
        raise ValueError('Chỉ nhận link video từ YouTube hoặc youtu.be.')
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', id):
        raise ValueError('Không tìm thấy mã video YouTube hợp lệ.')
    return 'https://www.youtube.com/watch?v=' + id


def source_path(value):
    path = Path(value).expanduser()
    host_root = Path(os.getenv('SOURCE_DIR', '/sources')).expanduser()
    if str(config.SOURCE_ROOT) == '/sources' and host_root.is_absolute() and path.is_relative_to(host_root):
        path = config.SOURCE_ROOT / path.relative_to(host_root)
    path = path.resolve()
    if not path.is_relative_to(config.SOURCE_ROOT):
        raise ValueError(f'Đường dẫn phải nằm trong thư mục nguồn được mount: {config.SOURCE_ROOT}')
    if not path.is_file():
        raise ValueError('Không tìm thấy file trong thư mục nguồn.')
    if path.stat().st_size > config.MAX_BYTES:
        raise ValueError('File lớn hơn giới hạn upload.')
    return path


def finish_source(source, path, title=None, preserve_analysis=False):
    info = probe(path)
    if not info.get('width') or info['duration'] <= 0 or not info['has_audio']:
        raise ValueError('Nguồn phải là video có âm thanh và thời lượng hợp lệ.')
    if info['duration'] > 8 * 3600:
        raise ValueError('Mỗi nguồn tối đa 8 giờ. Hãy chia nguồn dài hơn thành các phần.')
    folder = config.DATA / 'sources' / source['id']
    folder.mkdir(exist_ok=True)
    thumb = folder / 'thumbnail.jpg'
    frame(path, thumb, min(5, info['duration'] / 4))
    preview = path
    # Chromium can play the MP4 streams selected above (H.264, VP9 or AV1).
    # Keeping that original file for the editor avoids a 1280px proxy being
    # cropped and enlarged again in the portrait preview.  A proxy remains a
    # compatibility fallback for non-MP4 container uploads.
    if path.suffix.lower() not in ('.mp4', '.m4v'):
        preview = folder / 'preview.mp4'
        ffmpeg(['-i', path, '-vf', 'scale=1280:1280:force_original_aspect_ratio=decrease:force_divisible_by=2',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-c:a', 'aac', '-b:a', '128k',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', preview])
    status = 'analyzed' if preserve_analysis and source.get('transcript_ready') else 'ready'
    return store.update(source['id'], path=str(path.relative_to(config.DATA)), preview_path=str(preview.relative_to(config.DATA)), thumbnail=str(thumb.relative_to(config.DATA)), status=status, title=title or source['title'], **info)


def _youtube_download(source, progress, stem='original', preserve_analysis=False):
    """Download a new source beside the previous one, only switching on success."""
    import yt_dlp
    folder = config.DATA / 'sources' / source['id']
    url = youtube_url(source['input'])
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            if d.get('downloaded_bytes', 0) > config.MAX_BYTES:
                raise ValueError('Nguồn YouTube vượt giới hạn dung lượng.')
            percent = min(85, int(d.get('downloaded_bytes', 0) / total * 80)) if total else 20
            progress('Đang tải video YouTube chất lượng cao', percent)
    class QuietLogger:
        def debug(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): pass
    opts = {'outtmpl': str(folder / (stem + '.%(ext)s')), 'format': YOUTUBE_FORMAT,
            'merge_output_format': 'mp4', 'noplaylist': True, 'max_filesize': config.MAX_BYTES, 'socket_timeout': 30,
            'retries': 3, 'quiet': True, 'logger': QuietLogger(), 'progress_hooks': [hook],
            'js_runtimes': {'node': {}}, 'cachedir': str(config.DATA / 'youtube-cache')}
    with yt_dlp.YoutubeDL(opts) as dl:
        info = dl.extract_info(url, download=True)
    candidates = sorted((p for p in folder.glob(stem + '.*') if p.suffix.lower() in ('.mp4', '.mkv', '.webm')), key=lambda p:p.stat().st_mtime_ns, reverse=True)
    if not candidates:
        raise ValueError('Không tải được video. Link có thể yêu cầu đăng nhập; hãy upload file nguồn.')
    return finish_source(source, candidates[0], info.get('title', source['title']), preserve_analysis=preserve_analysis)


def import_source(source, progress):
    folder = config.DATA / 'sources' / source['id']
    folder.mkdir(exist_ok=True)
    if source['kind'] == 'path':
        path = source_path(source['input'])
        progress('Đang nhập video từ thư mục nguồn', 25)
        target = folder / ('original' + path.suffix.lower())
        shutil.copyfile(path, target)
        return finish_source(source, target, path.name)
    progress('Đang chọn stream YouTube chất lượng cao', 10)
    return _youtube_download(source, progress)


def refresh_youtube_quality(source, progress):
    if source.get('kind') != 'youtube':
        raise ValueError('Chỉ có thể tải lại chất lượng cho nguồn YouTube.')
    # Do not overwrite the working source.  Existing clips/transcripts continue
    # to point at their previous input until the new file has been fully probed.
    progress('Đang chọn stream 4K/2K từ YouTube', 5)
    result = _youtube_download(source, progress, stem='quality-' + uuid.uuid4().hex, preserve_analysis=True)
    # Generated card thumbnails are safe to refresh; transcript timing and clip
    # settings deliberately remain untouched.
    for clip in store.listing('clip'):
        if clip.get('source_id') != source['id']:
            continue
        target = config.DATA / 'sources' / source['id'] / f"clip-{clip['id']}.jpg"
        frame(config.DATA / result['path'], target, clip['start'])
        store.update(clip['id'], thumbnail=str(target.relative_to(config.DATA)))
    return result


def transcript_segments(words):
    result, group = [], []
    for w in words:
        if group and (w['start'] - group[0]['start'] > 12 or w.get('speaker') != group[-1].get('speaker') or w['start'] - group[-1]['end'] > 1):
            result.append({'start': group[0]['start'], 'end': group[-1]['end'], 'speaker': group[0].get('speaker', ''), 'text': ' '.join(x['text'] for x in group)})
            group = []
        group.append(w)
    if group:
        result.append({'start': group[0]['start'], 'end': group[-1]['end'], 'speaker': group[0].get('speaker', ''), 'text': ' '.join(x['text'] for x in group)})
    return result


def validate_candidates(raw, words, duration, min_seconds, max_seconds):
    candidates = []
    for item in raw[:80]:
        try:
            start, end = float(item['start']), float(item['end'])
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration + .2):
                continue
            selected = [w for w in words if w['end'] > start and w['start'] < end]
            if not selected:
                continue
            start = max(0, selected[0]['start'] - .12)
            end = min(duration, selected[-1]['end'] + .18)
            if not max(1, min_seconds - 2) <= end - start <= max_seconds + 2:
                continue
            if any(max(0, min(end, c['end']) - max(start, c['start'])) / min(end - start, c['end'] - c['start']) > .6 for c in candidates):
                continue
            candidates.append({'start': round(start, 3), 'end': round(end, 3), 'title': str(item['title'])[:180],
                               'summary': str(item.get('summary', ''))[:600], 'reason': str(item.get('reason', ''))[:1000],
                               'score': min(100, max(0, int(item.get('score', 70)))), 'topic': str(item.get('topic', 'Nội dung'))[:80],
                               'context_note': str(item.get('context_note', ''))[:1000], 'intro_text': str(item.get('intro_text', ''))[:700]})
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(candidates, key=lambda c: -c['score'])


def analyze(source, params, progress):
    folder = config.DATA / 'sources' / source['id']
    folder.mkdir(exist_ok=True)
    transcript_file = folder / 'transcript.json'
    words = []
    if transcript_file.exists():
        words = json.loads(transcript_file.read_text())
    else:
        # Five-minute chunks bound memory/network size; a two-second overlap protects boundary words.
        duration = source['duration']
        starts = list(range(0, math.ceil(duration), 300))
        for index, start in enumerate(starts):
            progress(f'Google STT đang nhận lời thoại · phần {index + 1}/{len(starts)}', 8 + int(index / len(starts) * 48))
            cached = folder / f'words-{index}.json'
            if cached.exists():
                chunk = json.loads(cached.read_text())
            else:
                audio = folder / f'audio-{index}.mp3'
                ffmpeg(['-ss', str(max(0, start - 2)), '-i', config.DATA / source['path'], '-t', str(min(302, duration - max(0, start - 2))), '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', audio])
                chunk = google_ai.transcribe(audio)
                cached.write_text(json.dumps(chunk, ensure_ascii=False))
                audio.unlink(missing_ok=True)
            base = max(0, start - 2)
            for w in chunk:
                w = Word.model_validate({**w, 'start': w['start'] + base, 'end': w['end'] + base}).model_dump()
                if w['end'] > duration + .1 or (words and w['start'] < words[-1]['end'] - .08):
                    continue
                words.append(w)
        transcript_file.write_text(json.dumps(words, ensure_ascii=False))
    segments = transcript_segments(words)
    store.update(source['id'], transcript=segments, word_count=len(words), transcript_ready=True)
    proposals = []
    # Long talks are evaluated in 15-minute windows with one minute of overlap.
    for window in range(0, math.ceil(source['duration']), 900):
        progress('Gemini 3.8 Flash đang tìm đoạn có giá trị', 60 + int(window / max(1, source['duration']) * 26))
        excerpt = [s for s in segments if window - 60 <= s['start'] < window + 900]
        prompt = f'''Chọn nhiều đoạn video ngắn độc lập, hoàn chỉnh ý, có giá trị xây kênh cho doanh nghiệp.
Chủ đề người dùng: {params['focus']}
Độ dài mỗi đoạn {params['min_seconds']} đến {params['max_seconds']} giây. Chỉ chọn nội dung có thật trong transcript, không ép khớp chủ đề nếu nguồn không liên quan.
Bắt đầu bằng câu có đủ chủ ngữ/ngữ cảnh, kết thúc trọn ý. Giữ điều kiện, ngoại lệ và phủ định; không cắt thành phát biểu thuế/tài chính sai nghĩa. Không bịa số liệu. Không cần số lượng cố định. Loại đoạn quảng cáo, im lặng, lan man, trùng ý.
Mốc start/end là GIÂY TUYỆT ĐỐI trong nguồn. Điểm score 0..100 là đánh giá biên tập, không phải xác suất viral.
JSON {{"clips":[{{"start":0,"end":60,"title":"tiêu đề ngắn hấp dẫn nhưng trung thực","summary":"tóm tắt 1-2 câu tối đa 45 từ để hiển thị khung mở đầu","intro_text":"lời mở đầu 1–2 câu dẫn vào vấn đề, khác tiêu đề, không thêm thông tin ngoài transcript","reason":"vì sao nên cắt","score":80,"topic":"chủ đề","context_note":"bối cảnh hoặc điều kiện cần giữ"}}]}}.
TRANSCRIPT DỮ LIỆU:\n{json.dumps(excerpt,ensure_ascii=False)}'''
        result = google_ai.generate(prompt)
        proposals.extend(result.get('clips', []))
    clips = validate_candidates(proposals, words, source['duration'], params['min_seconds'], params['max_seconds'])
    batch = []
    for clip in clips:
        item = store.create('clip', {**clip, 'source_id': source['id'], 'settings': Settings(crop_mode='auto',intro_text=str(clip.get('intro_text', ''))[:700]).model_dump(), 'status': 'draft', 'revision': 1})
        thumbnail = folder / f"clip-{item['id']}.jpg"
        frame(config.DATA / source['path'], thumbnail, clip['start'])
        store.update(item['id'], thumbnail=str(thumbnail.relative_to(config.DATA)))
        batch.append(item['id'])
    store.update(source['id'], status='analyzed', latest_clips=batch, focus=params['focus'])
    return {'clips': batch, 'message': f'Đã tìm thấy {len(batch)} đoạn phù hợp.' if batch else 'Không có đoạn khớp tiêu chí. Hãy đổi chủ đề hoặc thời lượng.'}


def dispatch(job, progress):
    kind, id = job['kind'], job['target']
    if kind == 'import':
        return import_source(store.get(id, 'source'), progress)
    if kind == 'refresh-quality':
        return refresh_youtube_quality(store.get(id, 'source'), progress)
    if kind == 'analyze':
        return analyze(store.get(id, 'source'), job['payload'], progress)
    if kind == 'focus':
        clip = job['payload']['clip']
        source = store.get(clip['source_id'], 'source')
        path = config.DATA / 'sources' / source['id'] / 'transcript.json'
        words = json.loads(path.read_text()) if path.exists() else []
        return editor.focus_track(config.DATA / source['path'], clip, config.DATA / 'jobs' / job['id'], progress, words)
    if kind == 'render':
        clip = job['payload']['clip']
        source = store.get(clip['source_id'], 'source')
        path = config.DATA / 'sources' / source['id'] / 'transcript.json'
        words = clip.get('words') if clip.get('words') is not None else json.loads(path.read_text()) if path.exists() else []
        target = config.DATA / 'renders' / job['id']
        output, info, track = editor.render(config.DATA / source['path'], clip, words, clip['settings'], target, progress)
        result = store.create('export', {'clip_id': clip['id'], 'source_id': source['id'], 'title': clip['title'], 'path': str(output.relative_to(config.DATA)), 'size': output.stat().st_size, 'revision': clip['revision'], 'focus': track, **info})
        store.update(id, last_export=result['id'])
        return result
    if kind == 'research':
        clip = store.get(id, 'clip')
        progress('Đang tìm nguồn đối chiếu bằng Google Search', 20)
        result = google_ai.generate('Tìm nguồn chính thức để đối chiếu nội dung sau tại thời điểm hiện tại. Phân biệt rõ lời nói trong video với thông tin đã kiểm tra. Nêu ngày của quy định nếu có, điều kiện áp dụng, điểm chưa xác minh. Không đưa tư vấn cá nhân. Kèm nguồn. Nội dung:\n' + clip['summary'], json_output=False, search=True)
        store.update(id, research=result)
        return result
    raise ValueError('Tác vụ không hợp lệ.')


def worker():
    while True:
        id = jobs.get()
        job = store.get(id, 'job')
        try:
            store.update(id, status='running')
            def progress(message, percent):
                store.update(id, message=message, progress=percent)
            result = dispatch(job, progress)
            store.update(id, status='completed', progress=100, message='Hoàn tất', result=result)
        except Exception as e:
            message = str(e).replace(config.API_KEY, '[redacted]') if config.API_KEY else str(e)
            store.update(id, status='failed', error=message[:1800], message='Cần xử lý lại')
            if job['kind'] == 'import':
                store.update(job['target'], status='failed')
        finally:
            jobs.task_done()


def start_worker():
    for job in reversed(store.listing('job')):
        if job['status'] == 'queued':
            jobs.put(job['id'])
        elif job['status'] == 'running':
            store.update(job['id'], status='failed', message='Tác vụ bị gián đoạn khi khởi động lại', error='Ứng dụng đã khởi động lại. Bấm thử lại; các phần transcript đã xong được giữ lại.')
    threading.Thread(target=worker, daemon=True, name='talkcut-worker').start()
