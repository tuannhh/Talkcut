import json
import math
import os
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from . import config, store, google_ai, editor
from .media import ffmpeg, probe, frame
from .schemas import Settings, Word

# Separate lanes so a long transcription never holds up an export and an
# export never holds up importing the next source. Each lane runs its own
# worker threads (config.LANE_WORKERS); heavy CPU lanes default to one.
LANES = {'render': ('render',), 'framing': ('focus', 'subject-gallery', 'stacked-view'), 'ingest': ('import', 'refresh-quality', 'proxy'),
         'ai': ('analyze', 'research', 'style-template')}
LANE_OF = {kind: lane for lane, kinds in LANES.items() for kind in kinds}
# Background preparation waits behind anything a person asked for.
INTERACTIVE, BACKGROUND = 0, 1
queues = {lane: queue.PriorityQueue() for lane in LANES}
submit_lock = threading.Lock()
claim_lock = threading.Lock()

# A landscape 1080p source only has about 608 pixels across a 9:16 crop.  It
# must then be enlarged to 1080px for the final video, which is visibly soft.
# Prefer a 2160p MP4 stream when YouTube offers it, while retaining sensible
# lower-resolution fallbacks for ordinary public videos.
YOUTUBE_FORMAT = 'bv*[height<=2160][ext=mp4]+ba[ext=m4a]/bv*[height<=2160]+ba/b[height<=2160]'


def enqueue(kind, target, payload=None, priority=INTERACTIVE):
    with submit_lock:
        active = next((j for j in store.listing('job') if j['kind'] == kind and j['target'] == target and j['status'] in ('queued', 'running')), None)
        if active:
            if active['status'] == 'queued' and priority < active.get('priority', INTERACTIVE):
                # Someone now waits for this background job: move it to the front.
                active = store.update(active['id'], priority=priority)
                _put(active)
            return active
        item = store.create('job', {'kind': kind, 'target': target, 'payload': payload or {}, 'status': 'queued', 'progress': 0,
                                    'message': 'Đang chờ xử lý', 'error': None, 'priority': priority})
        _put(item)
        return item


def _put(job):
    queues[LANE_OF.get(job['kind'], 'ai')].put((job.get('priority', INTERACTIVE), job['created'], job['id']))


def queue_positions(jobs):
    """Place in its lane for every queued job (1 = next), in the workers' own order."""
    waiting = sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (j.get('priority', INTERACTIVE), j['created']))
    seen, positions = {}, {}
    for job in waiting:
        lane = LANE_OF.get(job['kind'], 'ai')
        seen[lane] = seen.get(lane, 0) + 1
        positions[job['id']] = seen[lane]
    return positions


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
    proxy = needs_proxy(info, path)
    # Chromium can play the MP4 streams selected above (H.264, VP9 or AV1).
    # Keeping that original file for the editor avoids a 1280px proxy being
    # cropped and enlarged again in the portrait preview.  A proxy remains a
    # compatibility fallback for non-MP4 container uploads.
    if path.suffix.lower() not in ('.mp4', '.m4v') and not proxy:
        preview = folder / 'preview.mp4'
        ffmpeg(['-i', path, '-vf', 'scale=1280:1280:force_original_aspect_ratio=decrease:force_divisible_by=2',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-c:a', 'aac', '-b:a', '128k',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', preview])
    status = 'analyzed' if preserve_analysis and source.get('transcript_ready') else 'ready'
    updated = store.update(source['id'], path=str(path.relative_to(config.DATA)), preview_path=str(preview.relative_to(config.DATA)), thumbnail=str(thumb.relative_to(config.DATA)), status=status, title=title or source['title'], **info)
    if proxy:
        # The original plays meanwhile; the light copy replaces it when ready.
        enqueue('proxy', source['id'])
    return updated


PROXY_HEIGHT = 1080


def needs_proxy(info, path):
    """Office browsers decode 1080p H.264 in hardware; 4K, AV1 or HEVC sources stutter there."""
    if config.PREVIEW_PROXY != 'auto':
        return False
    return info.get('height', 0) > PROXY_HEIGHT or info.get('width', 0) > 1920 or info.get('codec') != 'h264' or path.suffix.lower() not in ('.mp4', '.m4v')


def make_proxy(source, progress):
    """1080p H.264 preview with a keyframe every second (fast seeking in the editor).
    Only the preview uses it; analysis and export always read the original."""
    from .media import ffmpeg_progress
    folder = config.DATA / 'sources' / source['id']
    target, temp = folder / 'preview-1080.mp4', folder / 'preview-1080.part.mp4'
    progress('Đang tạo bản xem trước nhẹ cho trình duyệt', 2)
    ffmpeg_progress(['-i', config.DATA / source['path'], '-map', '0:v:0', '-map', '0:a:0?',
                     '-vf', f'scale=1920:{PROXY_HEIGHT}:force_original_aspect_ratio=decrease:force_divisible_by=2',
                     '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-force_key_frames', 'expr:gte(t,n_forced)',
                     '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', temp],
                    source['duration'], lambda frac: progress('Đang tạo bản xem trước nhẹ cho trình duyệt', 2 + int(frac * 96)))
    temp.replace(target)
    store.update(source['id'], preview_path=str(target.relative_to(config.DATA)))
    return {'preview_path': str(target.relative_to(config.DATA))}


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


STT_CHUNK = 300
# Peak below this is a waiting screen or muted segment: nothing to transcribe.
SILENT_PEAK_DB = -50


def _chunk_words(source, folder, index, start):
    """Words of one five-minute chunk (times relative to the chunk audio), cached.
    Returns (words, gap) where gap marks audible audio that produced no words."""
    cached = folder / f'words-{index}.json'
    if cached.exists():
        return json.loads(cached.read_text()), None
    from .media import peak_db
    base = max(0, start - 2)
    audio = folder / f'audio-{index}.mp3'
    try:
        # A two-second overlap protects boundary words.
        ffmpeg(['-ss', str(base), '-i', config.DATA / source['path'], '-t', str(min(STT_CHUNK + 2, source['duration'] - base)),
                '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', audio])
        if peak_db(audio) < SILENT_PEAK_DB:
            chunk = []
        else:
            chunk = google_ai.transcribe(audio) or google_ai.transcribe(audio)  # one retry for an empty answer
            if not chunk:
                # Not cached: a later retry of the analysis asks Google again.
                return [], [round(base, 2), round(min(source['duration'], start + STT_CHUNK), 2)]
        cached.write_text(json.dumps(chunk, ensure_ascii=False))
        return chunk, None
    finally:
        audio.unlink(missing_ok=True)


def transcribe_source(source, folder, progress):
    """Measured word timings for the whole source. Five-minute chunks run in
    parallel; silent chunks are skipped instead of failing the long talk."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    duration = source['duration']
    starts = list(range(0, math.ceil(duration), STT_CHUNK))
    results, errors, done = {}, [], 0
    progress(f'Google STT đang nhận lời thoại · 0/{len(starts)} phần', 8)
    with ThreadPoolExecutor(max_workers=config.STT_PARALLEL) as pool:
        futures = {pool.submit(_chunk_words, source, folder, index, start): index for index, start in enumerate(starts)}
        for future in as_completed(futures):
            done += 1
            try:
                results[futures[future]] = future.result()
            except Exception as error:
                errors.append(error)
            progress(f'Google STT đang nhận lời thoại · {done}/{len(starts)} phần', 8 + int(done / len(starts) * 48))
    if errors:
        # Finished chunks stay cached; retrying the job only redoes the rest.
        raise errors[0]
    words, gaps = [], []
    for index, start in enumerate(starts):
        chunk, gap = results[index]
        if gap:
            gaps.append(gap)
        base = max(0, start - 2)
        for w in chunk:
            w = Word.model_validate({**w, 'start': w['start'] + base, 'end': w['end'] + base}).model_dump()
            if w['end'] > duration + .1 or (words and w['start'] < words[-1]['end'] - .08):
                continue
            words.append(w)
    if not words:
        raise google_ai.AIError('Google STT không trả mốc thời gian từng từ. Không thể tạo karaoke chính xác; hãy thử đoạn có giọng nói rõ hơn.')
    return words, gaps


def window_proposals(segments, window, params):
    excerpt = [s for s in segments if window - 60 <= s['start'] < window + 900]
    prompt = f'''Chọn nhiều đoạn video ngắn độc lập, hoàn chỉnh ý, có giá trị xây kênh cho doanh nghiệp.
Chủ đề người dùng: {params['focus']}
Độ dài mỗi đoạn {params['min_seconds']} đến {params['max_seconds']} giây. Chỉ chọn nội dung có thật trong transcript, không ép khớp chủ đề nếu nguồn không liên quan.
Bắt đầu bằng câu có đủ chủ ngữ/ngữ cảnh, kết thúc trọn ý. Giữ điều kiện, ngoại lệ và phủ định; không cắt thành phát biểu thuế/tài chính sai nghĩa. Không bịa số liệu. Không cần số lượng cố định. Loại đoạn quảng cáo, im lặng, lan man, trùng ý.
Mốc start/end là GIÂY TUYỆT ĐỐI trong nguồn. Điểm score 0..100 là đánh giá biên tập, không phải xác suất viral.
JSON {{"clips":[{{"start":0,"end":60,"title":"tiêu đề ngắn hấp dẫn nhưng trung thực","summary":"tóm tắt 1-2 câu tối đa 45 từ để hiển thị khung mở đầu","intro_text":"lời mở đầu 1–2 câu dẫn vào vấn đề, khác tiêu đề, không thêm thông tin ngoài transcript","reason":"vì sao nên cắt","score":80,"topic":"chủ đề","context_note":"bối cảnh hoặc điều kiện cần giữ"}}]}}.
TRANSCRIPT DỮ LIỆU:\n{json.dumps(excerpt,ensure_ascii=False)}'''
    return google_ai.generate(prompt).get('clips', [])


def analyze(source, params, progress):
    folder = config.DATA / 'sources' / source['id']
    folder.mkdir(exist_ok=True)
    transcript_file = folder / 'transcript.json'
    words = []
    if transcript_file.exists():
        words = json.loads(transcript_file.read_text())
    else:
        words, gaps = transcribe_source(source, folder, progress)
        transcript_file.write_text(json.dumps(words, ensure_ascii=False))
        store.update(source['id'], stt_gaps=gaps)
    segments = transcript_segments(words)
    store.update(source['id'], transcript=segments, word_count=len(words), transcript_ready=True)
    proposals = []
    # Long talks are evaluated in 15-minute windows with one minute of overlap;
    # the windows are independent requests, so they run side by side.
    from concurrent.futures import ThreadPoolExecutor
    windows = list(range(0, math.ceil(source['duration']), 900))
    progress('Gemini 3.8 Flash đang tìm đoạn có giá trị', 60)
    with ThreadPoolExecutor(max_workers=config.STT_PARALLEL) as pool:
        for found in pool.map(lambda window: window_proposals(segments, window, params), windows):
            proposals.extend(found)
    clips = validate_candidates(proposals, words, source['duration'], params['min_seconds'], params['max_seconds'])
    batch = []
    for clip in clips:
        item = store.create('clip', {**clip, 'source_id': source['id'], 'settings': Settings(crop_mode='auto',intro_text=str(clip.get('intro_text', ''))[:700]).model_dump(), 'status': 'draft', 'revision': 1})
        thumbnail = folder / f"clip-{item['id']}.jpg"
        frame(config.DATA / source['path'], thumbnail, clip['start'])
        store.update(item['id'], thumbnail=str(thumbnail.relative_to(config.DATA)))
        batch.append(item['id'])
    store.update(source['id'], status='analyzed', latest_clips=batch, focus=params['focus'])
    prepare_framing(source, batch)
    message = f'Đã tìm thấy {len(batch)} đoạn phù hợp.' if batch else 'Không có đoạn khớp tiêu chí. Hãy đổi chủ đề hoặc thời lượng.'
    gaps = store.get(source['id'], 'source').get('stt_gaps') or []
    if gaps:
        span = ', '.join(f'{clock(a)}–{clock(b)}' for a, b in gaps[:3]) + ('…' if len(gaps) > 3 else '')
        message += f' Google chưa nhận được lời thoại ở {span}; phụ đề ở đó sẽ trống.'
    return {'clips': batch, 'message': message}


def prepare_framing(source, clip_ids):
    """Queue the AI framing of the best-scored new clips behind interactive work,
    so they open ready instead of each person waiting for their own analysis."""
    if not config.PREPARE_FRAMING_TOP or source['width'] / source['height'] <= .57:
        return []
    clips = sorted((store.get(id, 'clip') for id in clip_ids), key=lambda c: -c.get('score', 0))[:config.PREPARE_FRAMING_TOP]
    return [enqueue('focus', clip['id'], {'clip': clip}, BACKGROUND)['id'] for clip in clips]


def clock(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}' if seconds >= 3600 else f'{seconds // 60}:{seconds % 60:02d}'


def dispatch(job, progress):
    kind, id = job['kind'], job['target']
    if kind == 'import':
        return import_source(store.get(id, 'source'), progress)
    if kind == 'refresh-quality':
        return refresh_youtube_quality(store.get(id, 'source'), progress)
    if kind == 'proxy':
        return make_proxy(store.get(id, 'source'), progress)
    if kind == 'analyze':
        return analyze(store.get(id, 'source'), job['payload'], progress)
    if kind == 'focus':
        clip = job['payload']['clip']
        source = store.get(clip['source_id'], 'source')
        path = config.DATA / 'sources' / source['id'] / 'transcript.json'
        words = json.loads(path.read_text()) if path.exists() else []
        plan = editor.focus_track(config.DATA / source['path'], clip, config.DATA / 'jobs' / job['id'], progress, words)
        # The cached plan stays on disk; the job record keeps only a summary.
        return {'ready': True, 'cast': plan.get('cast', []), 'cuts': len(plan.get('visual_cuts', []))}
    if kind == 'subject-gallery':
        from .subject_tracking import candidates
        clip=store.get(id,'clip');source=store.get(clip['source_id'],'source')
        return {'items':candidates(config.DATA/source['path'],clip,progress=progress,refresh=bool(job['payload'].get('refresh')))}
    if kind == 'style-template':
        from .style_templates import analyze as analyze_style
        return analyze_style(store.get(id,'style-template'),progress)
    if kind == 'stacked-view':
        from .stacked_view import detect
        clip=store.get(id,'clip');source=store.get(clip['source_id'],'source')
        return detect(config.DATA/source['path'],clip,progress)
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


def claim(id):
    """Mark a queued job running; None when it was taken, dismissed or is a stale duplicate."""
    with claim_lock:
        try:
            job = store.get(id, 'job')
        except KeyError:
            return None
        if job['status'] != 'queued':
            return None
        return store.update(id, status='running', started=time.time())


def run_job(job):
    id = job['id']
    # Records made by this job (clips, exports) belong to whoever queued it.
    token = store.actor.set(job.get('created_by'))
    try:
        def progress(message, percent):
            store.update(id, message=message, progress=percent)
        result = dispatch(job, progress)
        note = result.get('message') if isinstance(result, dict) and isinstance(result.get('message'), str) else None
        store.update(id, status='completed', progress=100, message=note or 'Hoàn tất', result=result)
    except Exception as e:
        message = str(e).replace(config.API_KEY, '[redacted]') if config.API_KEY else str(e)
        store.update(id, status='failed', error=message[:1800], message='Cần xử lý lại')
        if job['kind'] == 'import':
            store.update(job['target'], status='failed')
        if job['kind'] == 'style-template':
            store.update(job['target'], status='failed',error=message[:600])
    finally:
        store.actor.reset(token)


def worker(lane):
    while True:
        _, _, id = queues[lane].get()
        try:
            job = claim(id)
            if job:
                run_job(job)
        finally:
            queues[lane].task_done()


def start_worker():
    for job in reversed(store.listing('job')):
        if job['status'] == 'queued':
            _put(job)
        elif job['status'] == 'running':
            store.update(job['id'], status='failed', message='Tác vụ bị gián đoạn khi khởi động lại', error='Ứng dụng đã khởi động lại. Bấm thử lại; các phần transcript đã xong được giữ lại.')
    for lane in LANES:
        for n in range(config.LANE_WORKERS[lane]):
            threading.Thread(target=worker, args=(lane,), daemon=True, name=f'talkcut-{lane}-{n}').start()
