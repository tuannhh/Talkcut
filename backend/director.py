"""Local AI director: reframes a 16:9 talk show into 9:16 the way an editor would.

Every framing decision comes from faces the local SCRFD/ArcFace engine found in
the actual frames: who is on camera, where their eyes are and which way they
look.  Who is speaking comes from the transcript's diarized words, mapped to the
on-screen people by what the source camera showed while each voice spoke.
Gemini only reads transcript text, once per source, to say which voice is the
host; a language model never supplies face coordinates.

`analyze` is the expensive, cached pass.  `prepare` turns it into a plan for the
current settings and is cheap enough to run for every preview request, so the
browser preview and the FFmpeg export always read the same geometry.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
import shutil
import statistics
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import config
from .media import ffmpeg, run

VERSION = 'director-v1'
ROLES_VERSION = 'roles-v1'
SAMPLE_FPS = 2
FPS = 30
# pipeline.analyze transcribes in 5-minute requests; diarization labels are
# only consistent inside one request, so a voice is identified per chunk.
STT_CHUNK = 300
_lock = threading.RLock()

MIN_SCORE = .5
MIN_FACE_W, MIN_FACE_H = .018, .03
SAME_PERSON = .40
ATTACH_PERSON = .28
MIN_TURN = 1.2
MIN_SEGMENT = 1.0
MIN_STACKED = 1.2
EPS = 5e-4
HEAVY = ('samples', 'words', 'gaps')

SINGLE = {'aspect': 9 / 16, 'face_ratio': .19, 'eye_line': .31, 'min_crop_h': 820, 'lead': .1}
# Split-screen halves read tidier with faces near the middle: little look room.
HALF = {'aspect': 9 / 8, 'face_ratio': .30, 'eye_line': .42, 'min_crop_h': 420, 'lead': .04}
JUMP_PUNCH = 1.12
PAUSE_KEEP, TURN_KEEP = .16, .30


def cache_dir(source, clip):
    stat = Path(source).stat()
    identity = [VERSION, str(source), stat.st_size, stat.st_mtime_ns, round(clip['start'], 3), round(clip['end'], 3)]
    return config.DATA / 'jobs' / ('director-' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32])


def cached(source, clip):
    path = cache_dir(source, clip) / 'director.json'
    return json.loads(path.read_text()) if path.exists() else None


def voice(word):
    """Chunk-scoped diarization label: 'spk:0' in two STT requests may be two people."""
    return f"c{int(word['start'] // STT_CHUNK)}:{word['speaker']}" if word.get('speaker') else ''


# ---------------------------------------------------------------- analysis


def analyze(source, clip, progress=lambda *a: None, words=None):
    with _lock:
        found = cached(source, clip)
        if found:
            return found
        directory = cache_dir(source, clip)
        directory.mkdir(parents=True, exist_ok=True)
        duration = clip['end'] - clip['start']
        progress('Đang tách góc máy và lấy mẫu khung hình', 4)
        frames = _extract(source, clip, directory)
        from .focus import visual_layout
        layout = {}
        visual_layout(directory, layout)
        native = frame_differences(directory / 'mafd.txt')
        cuts = [c for c in refine_cuts(layout.get('visual_cuts', []), native) if 0 < c < duration]
        times = [i / SAMPLE_FPS for i in range(len(frames))]
        extra = _shot_fill_frames(source, clip, directory, cuts, times, duration)
        paths = [*frames, *(p for _, p in extra)]
        times = [*times, *(t for t, _ in extra)]
        detections = _detect(paths, progress)
        samples, vectors = observations(times, detections, cuts, duration, paths)
        progress('Đang nhận biết từng người trong clip', 84)
        people = cluster(tracklets(samples, vectors))
        label_people(samples, people)
        transcript = _transcript(source, clip, words)
        clip_words = _clip_words(clip, transcript)
        speakers, shares = speaker_map(samples, clip_words)
        progress('Đang xác định MC và khách mời', 88)
        hosts = host_voices(source, transcript)
        cast = _cast(samples, people, speakers, shares, hosts, clip_words, directory)
        progress('Đang tìm khoảng lặng và âm đệm', 93)
        gaps = audio_gaps(source, clip, clip_words)
        for sample in samples:
            sample.pop('path', None)
            for face in sample['faces']:
                face.pop('vector', None)
        steps = [b[0] - a[0] for a, b in zip(native, native[1:]) if b[0] > a[0]]
        result = {'version': VERSION, 'director': True, 'start': clip['start'], 'end': clip['end'],
                  'source_fps': round(1 / statistics.median(steps), 3) if steps else 30, 'visual_cuts': cuts,
                  'speech_turns': voice_turns(clip, transcript), 'samples': samples, 'words': clip_words,
                  'speakers': speakers, 'cast': cast, 'gaps': gaps,
                  'layout_version': 'portrait-v5.1', 'geometry_version': VERSION}
        shutil.rmtree(directory / 'frames', ignore_errors=True)
        temp = directory / (uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False))
        temp.replace(directory / 'director.json')
        return result


def _extract(source, clip, directory):
    """One decode: 6 fps scouting proxies for cut detection, 2 fps stills for faces and
    the native-rate frame difference that places each cut on its exact frame.

    round=up + start_time=0: still n shows the source at time n/2, never a frame
    from after it, so a still just before a cut cannot show the next shot."""
    frames = directory / 'frames'
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir()
    for old in directory.glob('shots-*.mp4'):
        old.unlink()
    differences = str(directory / 'mafd.txt').replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
    ffmpeg(['-ss', str(clip['start']), '-t', str(clip['end'] - clip['start']), '-i', source,
            '-filter_complex', f"[0:v]split=3[scout][still][tiny];[scout]fps=6:round=up:start_time=0,scale=720:-2[proxy];"
            f"[still]fps={SAMPLE_FPS}:round=up:start_time=0,scale='min(1600,iw)':-2[frames];"
            f"[tiny]scale=64:36:flags=area,format=gray,scdet=threshold=100,metadata=mode=print:key=lavfi.scd.mafd:file='{differences}',nullsink",
            '-map', '[proxy]', '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '24',
            '-force_key_frames', 'expr:gte(t,n_forced*30)', '-f', 'segment', '-segment_time', '30',
            '-reset_timestamps', '1', directory / 'shots-%d.mp4',
            '-map', '[frames]', '-q:v', '3', '-start_number', '0', frames / '%05d.jpg'])
    return sorted(frames.glob('[0-9]*.jpg'))


def frame_differences(path):
    """[(clip time of a source frame, mean change from the previous frame 0..100)]."""
    rows, time = [], None
    for line in Path(path).read_text().splitlines() if Path(path).exists() else []:
        if line.startswith('frame:'):
            time = float(line.rsplit('pts_time:', 1)[1])
        elif line.startswith('lavfi.scd.mafd=') and time is not None:
            rows.append((time, float(line.split('=', 1)[1])))
    return rows


def refine_cuts(cuts, native):
    """Move each scouting cut (6 fps) to the source frame where the picture changes,
    then onto the 30 fps output frame that first shows the new shot."""
    times = [t for t, _ in native]
    result = []
    for cut in cuts:
        lo, hi = bisect.bisect_left(times, cut - .3), bisect.bisect_right(times, cut + .12)
        best = max(native[lo:hi], key=lambda row: row[1], default=None)
        exact = best[0] if best and best[1] >= 5 else cut
        result.append(round(math.ceil(exact * FPS - 1e-4) / FPS, 4))
    return sorted(set(result))


def voice_turns(clip, words):
    """Continuous stretches of one diarized voice (manual framing uses these for holds)."""
    turns = []
    for w in words:
        if not w.get('speaker') or w['end'] <= clip['start'] or w['start'] >= clip['end']:
            continue
        a, b, key = max(0, w['start'] - clip['start']), min(clip['end'], w['end']) - clip['start'], voice(w)
        if turns and turns[-1]['speaker'] == key and a - turns[-1]['end'] < 2:
            turns[-1]['end'] = max(b, turns[-1]['end'])
        else:
            turns.append({'start': round(a, 3), 'end': round(b, 3), 'speaker': key})
    return turns


def _shot_fill_frames(source, clip, directory, cuts, times, duration):
    """A camera shot shorter than the sampling step still gets one real observation."""
    bounds = [0, *cuts, duration]
    extra = []
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        if b - a < .15 or any(a + .07 <= t < b - .07 for t in times):
            continue
        t = (a + b) / 2
        path = directory / 'frames' / f'shot-{i}.jpg'
        ffmpeg(['-ss', str(clip['start'] + t), '-i', source, '-frames:v', '1', '-vf', "scale='min(1600,iw)':-2", '-q:v', '3', path])
        if path.exists():
            extra.append((round(t, 4), path))
    return extra


def _detect(paths, progress):
    from .face_engine import describe
    workers = max(1, int(os.getenv('FACE_ENGINE_WORKERS', '2')))
    results = []
    with ThreadPoolExecutor(max_workers=workers + 1) as pool:
        for index, faces in enumerate(pool.map(lambda path: describe(Path(path).read_bytes()), paths), 1):
            results.append(faces)
            if index % 10 == 0 or index == len(paths):
                progress(f'Đang nhận diện khuôn mặt · {index}/{len(paths)} khung hình', 8 + int(index / max(1, len(paths)) * 74))
    return results


def _normalized(vector):
    vector = np.asarray(vector, np.float32)
    return vector / (np.linalg.norm(vector) or 1)


def observations(times, detections, cuts, duration, paths=None):
    """Keep clear faces; a frame exactly on a camera cut could belong to either shot."""
    rows = sorted(zip(times, detections, paths or [None] * len(times)), key=lambda row: row[0])
    samples, vectors = [], []
    for t, faces, path in rows:
        if t >= duration or any(abs(t - c) < .07 for c in cuts):
            continue
        kept = []
        for face in faces:
            x1, y1, x2, y2 = face['box']
            if face.get('score', 0) < MIN_SCORE or x2 - x1 < MIN_FACE_W or y2 - y1 < MIN_FACE_H:
                continue
            kept.append({'box': [round(v, 4) for v in face['box']], 'kps': face.get('kps'),
                         'score': round(face.get('score', 0), 3), 'vector': len(vectors)})
            vectors.append(_normalized(face['embedding']))
        sample = {'time': round(t, 4), 'shot': bisect.bisect_right(cuts, t), 'faces': kept}
        if path is not None:
            sample['path'] = str(path)
        samples.append(sample)
    return samples, (np.stack(vectors) if vectors else np.zeros((0, 512), np.float32))


def _iou(a, b):
    w = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inside = w * h
    return inside / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inside or 1)


def _center(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def tracklets(samples, vectors):
    """Link each face to the same face in nearby samples of one camera shot."""
    tracks, open_tracks, shot = [], [], None
    for index, sample in enumerate(samples):
        if sample['shot'] != shot:
            shot, open_tracks = sample['shot'], []
        pairs = []
        for fi, face in enumerate(sample['faces']):
            vector = vectors[face['vector']]
            for track in open_tracks:
                if index - track['last'] > 3:
                    continue
                last = samples[track['last']]['faces'][track['last_face']]['box']
                similarity = float(vector @ track['centroid'])
                overlap = _iou(face['box'], last)
                near = math.dist(_center(face['box']), _center(last)) / max(face['box'][2] - face['box'][0], last[2] - last[0])
                if (overlap > .15 or near < .9) and similarity > .2 or similarity > .55:
                    pairs.append((overlap + similarity - near * .1, fi, track))
        faces_used, tracks_used = set(), set()
        for _, fi, track in sorted(pairs, key=lambda row: -row[0]):
            if fi in faces_used or track['id'] in tracks_used:
                continue
            faces_used.add(fi)
            tracks_used.add(track['id'])
            _extend(track, index, fi, vectors, sample['faces'][fi])
        for fi, face in enumerate(sample['faces']):
            if fi not in faces_used:
                track = {'id': len(tracks), 'shot': shot, 'items': [], 'sum': np.zeros(vectors.shape[1], np.float64)}
                _extend(track, index, fi, vectors, face)
                tracks.append(track)
                open_tracks.append(track)
    return tracks


def _extend(track, index, face_index, vectors, face):
    track['items'].append((index, face_index))
    track['sum'] = track['sum'] + vectors[face['vector']]
    track['centroid'] = track['sum'] / (np.linalg.norm(track['sum']) or 1)
    track['last'], track['last_face'] = index, face_index
    face['track'] = track['id']


def cluster(tracks):
    """Group tracklets into people. Two faces seen in one frame are never one person."""
    n = len(tracks)
    if not n:
        return []
    sums = np.stack([t['sum'] for t in tracks]).astype(np.float64)
    weight = np.array([len(t['items']) for t in tracks], float)
    members = [[i] for i in range(n)]
    seen = [{i for i, _ in t['items']} for t in tracks]
    conflict = np.zeros((n, n), bool)
    for i in range(n):
        for j in range(i + 1, n):
            if seen[i] & seen[j]:
                conflict[i, j] = conflict[j, i] = True
    alive = list(range(n))

    def merge(threshold, eligible):
        while len(alive) > 1:
            index = np.array(alive)
            centroids = sums[index] / np.maximum(np.linalg.norm(sums[index], axis=1, keepdims=True), 1e-9)
            similarity = centroids @ centroids.T
            np.fill_diagonal(similarity, -1)
            similarity[conflict[np.ix_(index, index)]] = -1
            similarity[~eligible(index)] = -1
            i, j = np.unravel_index(int(np.argmax(similarity)), similarity.shape)
            if similarity[i, j] < threshold:
                return
            a, b = alive[i], alive[j]
            if weight[b] > weight[a]:
                a, b = b, a
            sums[a] += sums[b]
            weight[a] += weight[b]
            members[a] += members[b]
            conflict[a] |= conflict[b]
            conflict[:, a] |= conflict[:, b]
            alive.remove(b)

    merge(SAME_PERSON, lambda index: np.ones((len(index), len(index)), bool))

    # A sparsely detected angle (often a profile) joins the closest established person.
    def small_to_large(index):
        large = weight[index] >= .25 * weight[index].max()
        return np.logical_xor.outer(large, large)

    merge(ATTACH_PERSON, small_to_large)
    return sorted(({'tracks': members[i], 'weight': int(weight[i])} for i in alive), key=lambda c: -c['weight'])


def label_people(samples, people):
    person_of = {}
    for index, person in enumerate(people):
        person['id'] = f'p{index}' if person['weight'] >= 2 else None
        for track in person['tracks']:
            person_of[track] = person['id']
    for sample in samples:
        for face in sample['faces']:
            face['person'] = person_of.get(face.get('track'))


def _transcript(source, clip, words):
    if clip.get('words') is not None:
        return clip['words']
    if words:
        return words
    path = Path(source).parent / 'transcript.json'
    return json.loads(path.read_text()) if path.exists() else []


def _clip_words(clip, words):
    a, b = clip['start'], clip['end']
    return [[round(max(0, w['start'] - a), 3), round(min(b, w['end']) - a, 3), voice(w)]
            for w in words if w['end'] > a and w['start'] < b]


def _dominant(sample):
    faces = sorted((f for f in sample['faces'] if f.get('person')), key=lambda f: -_area(f['box']))
    if len(faces) == 1:
        return faces[0]['person']
    if len(faces) > 1 and _area(faces[0]['box']) >= 2.2 * _area(faces[1]['box']):
        return faces[0]['person']
    return None


def speaker_map(samples, words):
    """A talk-show camera mostly shows whoever is speaking; count that co-occurrence.

    Inside one STT chunk two voices never map to the same person."""
    times = [s['time'] for s in samples]
    seen, spoken = {}, {}
    for start, end, key in words:
        if not key:
            continue
        spoken[key] = spoken.get(key, 0) + end - start
        middle = (start + end) / 2
        i = bisect.bisect_left(times, middle)
        near = [k for k in (i - 1, i) if 0 <= k < len(times) and abs(times[k] - middle) <= .6]
        if not near:
            continue
        person = _dominant(samples[min(near, key=lambda k: abs(times[k] - middle))])
        if person:
            row = seen.setdefault(key, {})
            row[person] = row.get(person, 0) + end - start
    mapping, shares, chunks = {}, {}, {}
    for key in spoken:
        chunks.setdefault(key.split(':', 1)[0], []).append(key)
    for keys in chunks.values():
        pairs = sorted(((seconds / sum(seen[k].values()), seconds, k, p) for k in keys if k in seen for p, seconds in seen[k].items()), reverse=True)
        used = set()
        for share, _, key, person in pairs:
            if key in mapping or person in used or share < .4:
                continue
            mapping[key], shares[key] = person, round(share, 3)
            used.add(person)
        # Two voices, two people: a camera that rarely shows the host while they
        # ask questions must not leave the host unnamed.
        left = [k for k in keys if k not in mapping and spoken[k] >= 1.5]
        people = {p for k in keys for p in seen.get(k, {})} - used
        if len(left) == 1 and len(people) == 1 and len(used) == 1:
            mapping[left[0]], shares[left[0]] = people.pop(), 0
    return mapping, shares


QUESTION_ENDINGS = ('không', 'chưa', 'nào', 'sao', 'gì', 'nhỉ', 'hả', 'đâu', 'bao nhiêu', 'thế nào', 'đúng không', 'phải không')


def _turn_texts(words):
    turns = []
    for w in words:
        key = voice(w)
        if turns and turns[-1][0] == key and w['start'] - turns[-1][2] < 1.5:
            turns[-1][1].append(w.get('text', ''))
            turns[-1][2] = w['end']
        else:
            turns.append([key, [w.get('text', '')], w['end']])
    return [(key, ' '.join(texts).strip()) for key, texts, _ in turns if key]


def host_heuristic(words):
    """Per STT chunk: the host asks the questions and talks less than the guests."""
    turns = _turn_texts(words)
    counts = {}
    for w in words:
        if voice(w):
            counts[voice(w)] = counts.get(voice(w), 0) + 1
    chunks = {}
    for key in counts:
        chunks.setdefault(key.split(':', 1)[0], []).append(key)
    hosts = []
    for keys in chunks.values():
        if len(keys) < 2:
            continue
        total = sum(counts[k] for k in keys)
        scores = {}
        for key in keys:
            mine = [text for k, text in turns if k == key]
            asked = sum(text.endswith('?') or text.lower().rstrip(' .!…"”').endswith(QUESTION_ENDINGS) for text in mine)
            scores[key] = 2 * asked / max(1, len(mine)) + 1 - counts[key] / total
        hosts.append(max(scores, key=scores.get))
    return hosts


def host_voices(source, transcript):
    """Which chunk-scoped voices are the host. Cached per source; text only, no images."""
    keys = sorted({voice(w) for w in transcript if voice(w)})
    if len(keys) < 2:
        return []
    cache = Path(source).parent / f'{ROLES_VERSION}.json'
    if cache.exists():
        saved = json.loads(cache.read_text())
        if saved.get('keys') == keys:
            return saved.get('hosts', [])
    hosts, method = host_heuristic(transcript), 'heuristic'
    if config.API_KEY:
        try:
            found = _hosts_from_ai(transcript, keys)
            if found is not None:
                hosts, method = found, 'ai'
        except Exception:
            # Retry on a later analysis instead of caching a network failure.
            return hosts
    cache.write_text(json.dumps({'keys': keys, 'hosts': hosts, 'method': method}))
    return hosts


def _hosts_from_ai(words, keys):
    from . import google_ai
    counts = {k: sum(1 for w in words if voice(w) == k) for k in keys}
    per_chunk, excerpt = {}, []
    for key, text in _turn_texts(words):
        chunk = key.split(':', 1)[0]
        if per_chunk.get(chunk, 0) < 10:
            per_chunk[chunk] = per_chunk.get(chunk, 0) + 1
            excerpt.append(f'[{key}] ' + ' '.join(text.split()[:35]))
    prompt = ('Đây là transcript một talkshow/podcast. Nhãn người nói có dạng "c<phần>:<nhãn>"; mỗi phần được nhận dạng '
              'riêng, nên cùng nhãn ở hai phần khác nhau có thể là hai người khác nhau. Xác định các nhãn là MC/người dẫn '
              'chương trình (người đặt câu hỏi, dẫn dắt, giới thiệu khách mời). Chỉ dựa vào dữ liệu. '
              'JSON {"hosts":["c0:spk:1"],"confidence":0.9}. Nếu không có MC rõ ràng: {"hosts":[],"confidence":0}.\n'
              f'Số từ mỗi nhãn: {json.dumps(counts)}\nTRÍCH ĐOẠN:\n' + '\n'.join(excerpt))
    result = google_ai.generate(prompt)
    if not isinstance(result, dict) or float(result.get('confidence') or 0) < .6:
        return None
    return [k for k in result.get('hosts') or [] if k in keys] or None


def _cast(samples, people, speakers, shares, hosts, words, directory):
    spoken = {}
    for start, end, key in words:
        spoken[key] = spoken.get(key, 0) + end - start
    cast = []
    for person in people:
        if not person['id']:
            continue
        faces = [(s, f) for s in samples for f in s['faces'] if f.get('person') == person['id']]
        voices = [k for k, p in speakers.items() if p == person['id']]
        as_host = sum(spoken.get(k, 0) for k in voices if k in hosts)
        as_guest = sum(spoken.get(k, 0) for k in voices if k not in hosts)
        role = 'host' if voices and as_host > as_guest else 'guest' if voices else 'other'
        entry = {'id': person['id'], 'screen': round(len(faces) / SAMPLE_FPS, 1), 'voices': voices, 'role': role,
                 'speech': round(as_host + as_guest, 1), 'match': max((shares.get(k, 0) for k in voices), default=None)}
        best = max(faces, key=lambda row: _area(row[1]['box']) * row[1]['score'] * (1 - min(.6, abs(_yaw(row[1])))), default=None)
        if best and best[0].get('path'):
            entry['thumbnail'] = _thumbnail(best[0]['path'], best[1]['box'], directory / f'cast-{person["id"]}.jpg')
        cast.append(entry)
    return cast


def _thumbnail(frame_path, box, target):
    from PIL import Image
    with Image.open(frame_path) as image:
        w, h = image.size
        x1, y1, x2, y2 = box
        side = max((x2 - x1) * w, (y2 - y1) * h) * 1.8
        cx, cy = (x1 + x2) / 2 * w, (y1 + y2) / 2 * h
        left, top = max(0, cx - side / 2), max(0, cy - side / 2)
        image.crop((left, top, min(w, left + side), min(h, top + side))).convert('RGB').resize((160, 160)).save(target, quality=88)
    return str(target.relative_to(config.DATA))


# ---------------------------------------------------------------- audio


def audio_gaps(source, clip, words):
    duration = clip['end'] - clip['start']
    raw = run([config.FFMPEG, '-v', 'error', '-ss', str(clip['start']), '-t', str(duration), '-i', str(source),
               '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], 900)
    return gaps_from_signal(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, 16000, words, duration)


def envelope(signal, rate, hop=.01, window=.025):
    """Loudness in dB per 10 ms: index i covers time i/100."""
    h, w = int(rate * hop), int(rate * window)
    if len(signal) < w:
        return np.zeros(0)
    frames = np.lib.stride_tricks.sliding_window_view(signal, w)[::h]
    return 20 * np.log10(np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1)) + 1e-5)


def _runs(mask):
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def classify_gap(env, threshold):
    """silent: room tone/breath. filler: one sustained hesitation sound (ờ, ừm) the
    transcript left out. speech: syllables the transcript missed; never removed."""
    runs = [r for r in _runs(env > threshold) if r[1] - r[0] >= 7]
    if not runs:
        return 'silent'
    if len(runs) > 1 or runs[0][1] - runs[0][0] > 110:
        return 'speech'
    a, b = runs[0]
    smooth = np.convolve(env[a:b], np.ones(5) / 5, mode='same')
    peaks = [i for i in range(1, len(smooth) - 1) if smooth[i] >= smooth[i - 1] and smooth[i] > smooth[i + 1]]
    syllables = []
    for i in peaks:
        # A new syllable needs a dip of at least 6 dB between two loudness peaks.
        if syllables and smooth[syllables[-1]:i + 1].min() > min(smooth[syllables[-1]], smooth[i]) - 6:
            if smooth[i] > smooth[syllables[-1]]:
                syllables[-1] = i
            continue
        syllables.append(i)
    return 'filler' if len(syllables) <= 1 else 'speech'


def _quiet(env, threshold, index):
    window = env[max(0, index - 2):max(0, index + 3)]
    return bool(len(window)) and float(window.max()) < threshold - 6


def _cut(env, threshold, gap, keep, duration):
    """Removed span of one pause: both joins sit on quiet audio, never on a word edge."""
    start, end, edge = gap['start'], gap['end'], gap.get('edge')
    if edge == 'lead':
        a, b = 0, end - .12
    elif edge == 'tail':
        a, b = start + .3, duration
    else:
        a, b = start + keep / 2, end - keep / 2
    ia, ib = math.ceil(a * 100), math.floor(b * 100)
    if gap['kind'] == 'filler':
        vs, ve = gap['voiced']
        if vs - start < .06 or end - ve < .05:
            return None
        ia = min(ia, math.floor((vs - .04) * 100))
        ib = max(ib, math.ceil((ve + .04) * 100))
        while ia > (start + .03) * 100 and not _quiet(env, threshold, ia):
            ia -= 1
        while ib < (end - .03) * 100 and not _quiet(env, threshold, ib):
            ib += 1
        if not (_quiet(env, threshold, ia) and _quiet(env, threshold, ib)):
            return None
    else:
        if edge != 'lead':
            while ia < ib and not _quiet(env, threshold, ia):
                ia += 1
        if edge != 'tail':
            while ib > ia and not _quiet(env, threshold, ib):
                ib -= 1
    a = 0 if edge == 'lead' else math.ceil(ia / 100 * FPS - 1e-6) / FPS
    b = math.floor((duration if edge == 'tail' else ib / 100) * FPS + 1e-6) / FPS
    return [round(a, 4), round(b, 4)] if b - a >= .2 else None


def gaps_from_signal(signal, rate, words, duration):
    env = envelope(signal, rate)

    def span(a, b):
        return env[max(0, int(a * 100)):max(0, int(b * 100))]

    speech = [span(s, e) for s, e, _ in words]
    speech = np.concatenate(speech) if speech and sum(map(len, speech)) else env
    reference = float(np.percentile(speech, 90)) if len(speech) else -20
    threshold = max(-55, reference - 24)
    bounds = []
    if words:
        bounds.append((0, words[0][0], None, words[0][2], 'lead'))
        bounds += [(e1, s2, k1, k2, None) for (_, e1, k1), (s2, _, k2) in zip(words, words[1:])]
        bounds.append((words[-1][1], duration, words[-1][2], None, 'tail'))
    gaps = []
    for a, b, before, after, edge in bounds:
        if b - a < .28:
            continue
        inner = span(a + .06, b - .06)
        gap = {'start': round(a, 3), 'end': round(b, 3), 'kind': classify_gap(inner, threshold),
               'turn_change': bool(before and after and before != after)}
        if edge:
            gap['edge'] = edge
        if gap['kind'] == 'filler':
            first, last = max(_runs(inner > threshold), key=lambda r: r[1] - r[0])
            gap['voiced'] = [round(a + .06 + first / 100, 3), round(a + .06 + last / 100, 3)]
        if gap['kind'] != 'speech':
            gap['cut'] = _cut(env, threshold, gap, TURN_KEEP if gap['turn_change'] else PAUSE_KEEP, duration)
        gaps.append(gap)
    return gaps


def removals(gaps, enabled=True):
    """Tightened pauses. Boundaries sit on the 30 fps grid so kept video frames and
    kept audio samples always have identical length."""
    return sorted(g['cut'] for g in gaps if g.get('cut')) if enabled else []


def kept_intervals(removed, duration):
    edge = math.floor(duration * FPS + 1e-6) / FPS
    kept, cursor = [], 0
    for a, b in sorted(removed):
        if a > cursor:
            kept.append([round(cursor, 4), round(a, 4)])
        cursor = max(cursor, b)
    if cursor < edge:
        kept.append([round(cursor, 4), round(edge, 4)])
    return kept


# ---------------------------------------------------------------- directing


def speaking_turns(words, speakers):
    turns = []
    for start, end, key in words:
        if not key:
            continue
        if turns and turns[-1]['voice'] == key and start - turns[-1]['end'] < .8:
            turns[-1]['end'] = end
        else:
            turns.append({'start': start, 'end': end, 'voice': key, 'person': speakers.get(key), 'before': None})
    for previous, turn in zip(turns, turns[1:]):
        turn['before'] = previous['end']
    return turns


def shot_subjects(rows):
    """Clearly visible people in one camera shot; small background faces are ignored."""
    groups = {}
    for sample in rows:
        for face in sample['faces']:
            key = face.get('person') or f"track:{face.get('track')}"
            groups.setdefault(key, []).append((sample['time'], face))
    if not groups:
        return []
    heights = {key: statistics.median(f['box'][3] - f['box'][1] for _, f in obs) for key, obs in groups.items()}
    tallest = max(heights.values())
    subjects = []
    for key, obs in groups.items():
        presence = len({t for t, _ in obs}) / max(1, len(rows))
        if presence < .25 or heights[key] < .45 * tallest:
            continue
        left = statistics.median(f['box'][0] for _, f in obs)
        right = statistics.median(f['box'][2] for _, f in obs)
        subjects.append({'key': key, 'person': None if key.startswith('track:') else key, 'obs': obs, 'height': heights[key],
                         'center': (left + right) / 2, 'partial': left <= .004 or right >= .996})
    return sorted(subjects, key=lambda s: s['center'])


def _speech(turns, person, a, b):
    return sum(max(0, min(t['end'], b) - max(t['start'], a)) for t in turns if person and t['person'] == person)


def _kind(subject, turns, a, b):
    mine = _speech(turns, subject['person'], a, b)
    others = sum(max(0, min(t['end'], b) - max(t['start'], a)) for t in turns if not subject['person'] or t['person'] != subject['person'])
    return 'reaction' if others > max(.4, mine * 1.5) else 'speaker'


def _switch_time(turn):
    """Cut just before the new voice, never before the previous one finished."""
    start = turn['start']
    before = turn['before'] if turn['before'] is not None else start - .5
    cut = max(before + .04, start - .12) if start > before else start
    return math.ceil(cut * FPS - 1e-6) / FPS


def virtual_camera(a, b, subjects, turns):
    """Inside a wide shot, cut the virtual camera to whoever holds the floor."""
    visible = {s['person']: s for s in subjects if s['person']}
    inside = [t for t in turns if t['end'] > a and t['start'] < b]
    current = next((visible[t['person']] for t in inside if t['start'] <= a + .3 and t['person'] in visible), None)
    if current is None:
        current = next((visible[t['person']] for t in reversed([t for t in turns if t['end'] <= a]) if t['person'] in visible), None)
    if current is None:
        current = next((visible[t['person']] for t in inside if t['person'] in visible), None)
    if current is None:
        current = max(subjects, key=lambda s: s['height'])
    cuts = [(a, current)]
    for turn in inside:
        subject = visible.get(turn['person'])
        if subject is None or subject is current or min(turn['end'], b) - max(turn['start'], a) < MIN_TURN:
            continue
        cut = max(a, _switch_time(turn))
        if cut - cuts[-1][0] < MIN_SEGMENT or b - cut < MIN_SEGMENT:
            continue
        cuts.append((cut, subject))
        current = subject
    segments = []
    for i, (start, subject) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else b
        kind = _kind(subject, turns, start, end)
        segments.append({'start': start, 'end': end, 'layout': 'single', 'subject': subject, 'kind': kind, 'virtual': i > 0,
                         'reason': 'Cảnh toàn: máy quay ảo chọn người đang nói, giữ trọn khuôn mặt.' if kind == 'speaker' else 'Cảnh toàn: giữ trọn người trong khung khi chưa rõ ai đang nói.'})
    return segments


def roles(cast, swap=False):
    result = {c['id']: c['role'] for c in cast}
    if swap:
        hosts = [c['id'] for c in cast if c['role'] == 'host']
        guests = [c['id'] for c in sorted(cast, key=lambda c: -c['speech']) if c['role'] == 'guest']
        if hosts and guests:
            result[hosts[0]], result[guests[0]] = 'guest', 'host'
        elif len(cast) >= 2:
            # Without detected roles the two most visible people trade places.
            result[cast[0]['id']], result[cast[1]['id']] = 'host', 'guest'
    return result


def stack_pair(subjects, role_of, turns, a, b):
    """Guest on top, host below. Without known roles, the voice heard more goes on top."""
    people = [s for s in subjects if s['person'] and not s['partial']]
    if len(people) < 2:
        return None
    hosts = [s for s in people if role_of.get(s['person']) == 'host']
    others = [s for s in people if s not in hosts]
    if hosts and others:
        return max(others, key=lambda s: (_speech(turns, s['person'], a, b), s['height'])), hosts[0]
    ranked = sorted(people, key=lambda s: (role_of.get(s['person']) != 'guest', -_speech(turns, s['person'], 0, 1e9), -s['height']))
    return ranked[0], ranked[1]


def direct(analysis, settings):
    duration = analysis['end'] - analysis['start']
    turns = speaking_turns(analysis.get('words', []), analysis.get('speakers', {}))
    role_of = roles(analysis.get('cast', []), settings.get('swap_roles'))
    by_shot = {}
    for sample in analysis['samples']:
        by_shot.setdefault(sample['shot'], []).append(sample)
    bounds = [0, *analysis['visual_cuts'], duration]
    segments = []
    for shot, (a, b) in enumerate(zip(bounds, bounds[1:])):
        subjects = shot_subjects(by_shot.get(shot, []))
        whole = [s for s in subjects if not s['partial']] or subjects
        if not whole:
            segments.append({'shot': shot, 'start': a, 'end': b, 'layout': 'fill', 'kind': 'empty',
                             'reason': 'Không thấy khuôn mặt rõ: giữ toàn khung trên nền mờ.'})
        elif len(whole) == 1:
            kind = _kind(whole[0], turns, a, b)
            segments.append({'shot': shot, 'start': a, 'end': b, 'layout': 'single', 'subject': whole[0], 'kind': kind,
                             'reason': 'Người đang nói: khung theo mắt và hướng nhìn.' if kind == 'speaker' else 'Góc máy người nghe: giữ trọn khuôn mặt, lời thoại tiếp tục.'})
        else:
            pair = stack_pair(whole, role_of, turns, a, b) if settings.get('stacked_enabled') and b - a >= MIN_STACKED else None
            if pair:
                segments.append({'shot': shot, 'start': a, 'end': b, 'layout': 'stacked', 'kind': 'stacked', 'subject': pair[0], 'top': pair[0], 'bottom': pair[1],
                                 'reason': 'Cảnh toàn hai người: khách mời ở trên, MC ở dưới.'})
            else:
                segments += [{'shot': shot, **seg} for seg in virtual_camera(a, b, whole, turns)]
    return segments


def punch_jumps(segments, removed):
    """Alternate a slightly tighter size after each jump cut so it reads as intentional."""
    result = []
    for seg in segments:
        points = [r[1] for r in removed if seg['start'] + .3 < r[1] < seg['end'] - .3] if seg['layout'] == 'single' else []
        start, level, jump = seg['start'], 0, False
        for point in points:
            if point - start < 1.2 or seg['end'] - point < 1.2:
                continue
            result.append({**seg, 'start': start, 'end': point, 'punch': level, 'jump': jump})
            start, level, jump = point, level ^ 1, True
        result.append({**seg, 'start': start, 'end': seg['end'], 'punch': level, 'jump': jump})
    return result


# ---------------------------------------------------------------- composition


def _yaw(face):
    """Nose offset from the eye midpoint, in eye distances: + looks toward frame right."""
    kps = face.get('kps')
    if not kps:
        return 0
    (lx, _), (rx, _), (nx, _) = kps[0], kps[1], kps[2]
    return max(-1.5, min(1.5, (nx - (lx + rx) / 2) / max(abs(rx - lx), 1e-3)))


def _eyes(face):
    kps = face.get('kps')
    if kps:
        return (kps[0][1] + kps[1][1]) / 2
    return face['box'][1] + .4 * (face['box'][3] - face['box'][1])


def _even(value):
    return max(2, int(value) // 2 * 2)


def _window(lo, hi, low, high, fallback):
    """Feasible crop-center interval, clamped to the image."""
    if lo > hi:
        c = min(high, max(low, fallback))
        return c, c
    a, b = max(lo, low), min(hi, high)
    if a > b:
        c = min(high, max(low, (lo + hi) / 2))
        return c, c
    return a, b


def crop_size(info, style, face_height, zoom_min=1.0, punch=True, zoom_extra=1.0):
    iw, ih = info['width'], info['height']
    base_w = min(iw, ih * style['aspect'])
    base_h = base_w / style['aspect']
    cap = max(zoom_min, min(3.0, base_h / style['min_crop_h']))
    z = max(zoom_min, style['face_ratio'] * base_h / max(1, face_height * ih)) if punch else zoom_min
    z = min(cap, min(z, cap) * zoom_extra)
    return _even(base_w / z), _even(base_h / z)


def _avoid(x, lo, hi, wn, others):
    """Never leave half of another face at the frame edge: exclude it or include all of it."""
    for _ in range(2):
        for box in others:
            ow = box[2] - box[0]
            left, right = box[0] - .1 * ow, box[2] + .1 * ow
            covered = max(0, min(right, x + wn / 2) - max(left, x - wn / 2)) / (right - left)
            if covered <= .02 or covered >= .98:
                continue
            options = [left - wn / 2, right + wn / 2]
            if right - left <= wn:
                options.append(min(left + wn / 2, max(right - wn / 2, x)))
            options = [o for o in options if lo - 1e-9 <= o <= hi + 1e-9]
            if options:
                x = min(options, key=lambda o: abs(o - x))
    return x


def safe_box(face):
    """The whole head, not just the detected face: hair above, chin below and, for a
    turned head, the back of the skull the face box leaves out."""
    x1, y1, x2, y2 = face['box']
    fw, fh = x2 - x1, y2 - y1
    yaw = _yaw(face)
    back = min(1, abs(yaw))
    return (x1 - (.22 + (back if yaw > 0 else 0)) * fw, y1 - .38 * fh,
            x2 + (.22 + (back if yaw < 0 else 0)) * fw, y2 + .3 * fh)


def compose(info, obs, others, style, size, start):
    """One locked window for the whole segment when the subject allows it; otherwise
    a damped follow that still keeps every observed face fully inside."""
    iw, ih = info['width'], info['height']
    cw, ch = size
    wn, hn = min(1, cw / iw), min(1, ch / ih)
    obs = sorted(obs, key=lambda row: row[0])
    boxes = [safe_box(face) for _, face in obs]
    plans = []
    for i, (t, face) in enumerate(obs):
        x1, y1, x2, y2 = face['box']
        # Look room: leave space on the side the face is turned to.
        want_x = (x1 + x2) / 2 + style['lead'] * wn * max(-1, min(1, _yaw(face) * 1.8))
        want_y = _eyes(face) + (.5 - style['eye_line']) * hn
        # Between two samples the head travels; hold the neighbours' heads too.
        near = boxes[max(0, i - 1):i + 2]
        left, top = min(b[0] for b in near), min(b[1] for b in near)
        right, bottom = max(b[2] for b in near), max(b[3] for b in near)
        if right - left > wn or bottom - top > hn:
            left, top, right, bottom = boxes[i]
        xr = _window(right - wn / 2, left + wn / 2, wn / 2, 1 - wn / 2, (x1 + x2) / 2)
        yr = _window(bottom - hn / 2, top + hn / 2, hn / 2, 1 - hn / 2, (y1 + y2) / 2)
        plans.append((t, want_x, want_y, xr, yr))
    if not plans:
        return {'cw': cw, 'ch': ch, 'path': [(start, .5, .5)]}
    lo_x, hi_x = max(p[3][0] for p in plans), min(p[3][1] for p in plans)
    lo_y, hi_y = max(p[4][0] for p in plans), min(p[4][1] for p in plans)
    if lo_x <= hi_x + 1e-9 and lo_y <= hi_y + 1e-9:
        x = max(lo_x, min(hi_x, statistics.median(p[1] for p in plans)))
        y = max(lo_y, min(hi_y, statistics.median(p[2] for p in plans)))
        return {'cw': cw, 'ch': ch, 'path': [(start, _avoid(x, lo_x, hi_x, wn, others), y)]}
    path, x, y = [], None, None
    for t, want_x, want_y, xr, yr in plans:
        tx, ty = max(xr[0], min(xr[1], want_x)), max(yr[0], min(yr[1], want_y))
        if x is None:
            x, y = tx, ty
        else:
            x = x if abs(tx - x) < .06 * wn else x + (tx - x) * .6
            y = y if abs(ty - y) < .06 * hn else y + (ty - y) * .6
            x, y = max(xr[0], min(xr[1], x)), max(yr[0], min(yr[1], y))
        if not path or abs(x - path[-1][1]) > 1e-4 or abs(y - path[-1][2]) > 1e-4:
            path.append((max(start, t), x, y))
    path[0] = (start, path[0][1], path[0][2])
    return {'cw': cw, 'ch': ch, 'path': path}


def _obs(subject, a, b):
    return [(t, f) for t, f in subject['obs'] if a <= t < b] or subject['obs']


def _others(faces, subject, a, b):
    mine = {id(f) for _, f in subject['obs']}
    return [f['box'] for t, f in faces if a - .3 <= t < b + .3 and id(f) not in mine]


def prepare(analysis, info, settings):
    duration = analysis['end'] - analysis['start']
    zoom_min = settings.get('crop_zoom', 1) or 1
    punch = settings.get('punch_in', True)
    segments = direct(analysis, settings)
    faces_by_shot = {}
    for sample in analysis['samples']:
        faces_by_shot.setdefault(sample['shot'], []).extend((sample['time'], f) for f in sample['faces'])
    removed = removals(analysis.get('gaps', []), settings.get('silence_trim', True))
    if punch:
        segments = punch_jumps(segments, removed)
    iw, ih = info['width'], info['height']
    base_w, base_h = _even(min(iw, ih * 9 / 16) / zoom_min), _even(min(ih, iw * 16 / 9) / zoom_min)
    half_sizes = {}
    for role in ('top', 'bottom'):
        heights = [f['box'][3] - f['box'][1] for seg in segments if seg['layout'] == 'stacked' for _, f in _obs(seg[role], seg['start'], seg['end'])]
        if heights:
            half_sizes[role] = crop_size(info, HALF, statistics.median(heights))
    role_of = roles(analysis.get('cast', []), settings.get('swap_roles'))
    points, stacked, scenes = [], [], []
    for index, seg in enumerate(segments):
        a, b = seg['start'], seg['end']
        faces = faces_by_shot.get(seg['shot'], [])
        scenes.append({'start': round(a, 3), 'end': round(b, 3), 'kind': seg['kind'], 'layout': seg['layout'], 'reason': seg['reason']})
        if seg['layout'] == 'fill':
            points.append({'time': round(a, 4), 'mode': 'fit', 'x': .5, 'y': .5, 'cw': base_w, 'ch': base_h, 'cut': True, 'scene': index, 'kind': seg['kind']})
            continue
        subject = seg['subject']
        obs = _obs(subject, a, b)
        size = crop_size(info, SINGLE, statistics.median(f['box'][3] - f['box'][1] for _, f in obs), zoom_min, punch,
                         JUMP_PUNCH if seg.get('punch') else 1.0)
        frame = compose(info, obs, _others(faces, subject, a, b), SINGLE, size, a)
        for j, (t, x, y) in enumerate(frame['path']):
            point = {'time': round(t, 4), 'mode': 'crop', 'x': round(x, 5), 'y': round(y, 5), 'cw': frame['cw'], 'ch': frame['ch'],
                     'cut': j == 0, 'scene': index, 'kind': seg['kind'], 'person': subject['person']}
            if j == 0 and seg.get('jump'):
                point['jump'] = True
            points.append(point)
        if seg['layout'] == 'stacked':
            halves = {}
            for role in ('top', 'bottom'):
                person = seg[role]
                half = compose(info, _obs(person, a, b), _others(faces, person, a, b), HALF, half_sizes[role], a)
                _, x, y = half['path'][0]
                halves[role] = {'x': round(x, 5), 'y': round(y, 5), 'cw': half['cw'], 'ch': half['ch'], 'person': person['person']}
            stacked.append({'start': round(a, 4), 'end': round(b, 4), **halves})
    cuts = sorted({p['time'] for p in points if p['cut'] and not p.get('jump') and p['time'] > 0})
    cast = [{**c, 'role': role_of.get(c['id'], c['role'])} for c in analysis.get('cast', [])]
    kept = kept_intervals(removed, duration)
    removed_seconds = round(sum(b - a for a, b in removed), 2)
    switches = sum(bool(s.get('virtual')) and not s.get('jump') for s in segments)
    note = f"AI đạo diễn · {len(stacked)} cảnh ghép khung · {switches} lần máy quay ảo chuyển người nói"
    if removed_seconds:
        note += f' · rút {removed_seconds:.1f} giây khoảng lặng'
    return {**{k: v for k, v in analysis.items() if k not in HEAVY}, 'keyframes': points, 'visual_cuts': cuts, 'holds': [],
            'prepared': True, 'prepared_zoom': zoom_min, 'scenes': scenes, 'stacked': stacked, 'removed': removed,
            'removed_seconds': removed_seconds, 'kept_duration': round(sum(b - a for a, b in kept), 4),
            'cast': cast, 'note': note + '.'}


# ---------------------------------------------------------------- rendering


def _piecewise(points, values, variable):
    from .editor import balanced_sum
    terms = [f'{values[0]:.3f}']
    for i in range(len(points) - 1):
        p, q = points[i], points[i + 1]
        change = values[i + 1] - values[i]
        if abs(change) < 1e-3:
            continue
        if q.get('cut') or p.get('scene') != q.get('scene') or p.get('mode') != q.get('mode'):
            # A cut lands on the frame at its time even when rounding put it 0.1 ms late.
            terms.append(f'({change:.4f})*gte({variable},{q["time"] - EPS:.4f})')
        else:
            terms.append(f'({change:.4f})*clip(({variable}-{p["time"]:.4f})/{max(.01, q["time"] - p["time"]):.4f},0,1)')
    return balanced_sum(terms)


def strip_size(info, settings):
    zoom_min = settings.get('crop_zoom', 1) or 1
    return _even(min(info['width'], info['height'] * 9 / 16) / zoom_min), _even(min(info['height'], info['width'] * 16 / 9) / zoom_min)


def fill_intervals(prepared):
    points, end = prepared['keyframes'], round(prepared['end'] - prepared['start'], 4)
    return [(p['time'], next((q['time'] for q in points[i + 1:] if q['scene'] != p['scene']), end))
            for i, p in enumerate(points) if p['mode'] == 'fit']


def single_graph(info, settings, prepared):
    """Crop a full-size 9:16 strip, then zoompan inside it: per-segment crop sizes
    (punch-in on wide shots) with one scaling step per frame."""
    from .editor import balanced_sum
    iw, ih = info['width'], info['height']
    sw, sh = strip_size(info, settings)
    points = prepared['keyframes']
    if not points:
        return f'crop={sw}:{sh},scale=1080:1920:flags=lanczos,setsar=1'
    rows, last = [], None
    for p in points:
        if p['mode'] != 'crop' and last:
            rows.append(last)
            continue
        cw, ch = min(p['cw'], sw), min(p['ch'], sh)
        left = max(0, min(iw - cw, p['x'] * iw - cw / 2))
        top = max(0, min(ih - ch, p['y'] * ih - ch / 2))
        sx = max(0, min(iw - sw, left + cw / 2 - sw / 2))
        sy = max(0, min(ih - sh, top + ch / 2 - sh / 2))
        last = (sx, sy, left - sx, top - sy, sw / cw)
        rows.append(last)
    columns = list(zip(*rows))
    graph = (f"crop={sw}:{sh}:x='{_piecewise(points, columns[0], 't')}':y='{_piecewise(points, columns[1], 't')}',"
             f"zoompan=z='{_piecewise(points, columns[4], 'it')}':x='{_piecewise(points, columns[2], 'it')}':y='{_piecewise(points, columns[3], 'it')}'"
             f":d=1:s=1080x1920:fps={FPS},setsar=1")
    fills = fill_intervals(prepared)
    if not fills:
        return graph
    enable = balanced_sum([f'gte(t,{a - EPS:.4f})*lt(t,{b - EPS:.4f})' for a, b in fills])
    return (f"split=2[dir_main][dir_fill];[dir_main]{graph}[dir_tight];"
            f"[dir_fill]split=2[dir_fb][dir_ff];"
            f"[dir_fb]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,scale=1080:1920,setsar=1[dir_bg];"
            f"[dir_ff]scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1[dir_fg];"
            f"[dir_bg][dir_fg]overlay=(W-w)/2:(H-h)/2[dir_wide];"
            f"[dir_tight][dir_wide]overlay=0:0:shortest=1:enable='{enable}'")


def stacked_graph(info, stacked, duration):
    from .editor import balanced_sum
    from .stacked_view import SEAM_BLUR, SEAM_HEIGHT, seam_mask_asset
    iw, ih = info['width'], info['height']
    # A finite mask: an endless looped image would keep every downstream
    # overlay alive after the source ends, and select drops those frames.
    frames = math.ceil(duration * FPS) + FPS

    def crop(role):
        w, h = stacked[0][role]['cw'], stacked[0][role]['ch']
        xs = [max(0, min(iw - w, s[role]['x'] * iw - w / 2)) for s in stacked]
        ys = [max(0, min(ih - h, s[role]['y'] * ih - h / 2)) for s in stacked]

        def steps(values):
            return balanced_sum([f'{values[0]:.2f}'] + [f'({values[i] - values[i - 1]:.2f})*gte(t,{stacked[i]["start"] - EPS:.4f})'
                                                        for i in range(1, len(values)) if abs(values[i] - values[i - 1]) >= .5])
        return f"crop={w}:{h}:x='{steps(xs)}':y='{steps(ys)}',scale=1080:960:flags=lanczos,setsar=1"

    mask = str(seam_mask_asset()).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
    seam_y = 960 - SEAM_HEIGHT // 2
    return (f"split=2[dv_ti][dv_bi];[dv_ti]{crop('top')}[dv_t];[dv_bi]{crop('bottom')}[dv_b];"
            f"[dv_t][dv_b]vstack=inputs=2,split=2[dv_base][dv_seamsrc];"
            f"[dv_seamsrc]crop=1080:{SEAM_HEIGHT}:0:{seam_y},boxblur={SEAM_BLUR}:{SEAM_BLUR}[dv_blur];"
            f"movie='{mask}',loop=loop={frames}:size=1:start=0,setpts=N/{FPS}/TB,format=gray[dv_mask];"
            f"[dv_blur][dv_mask]alphamerge[dv_seam];[dv_base][dv_seam]overlay=0:{seam_y}:shortest=1")


def video_filter(info, settings, prepared, captions=None):
    """The whole export picture chain. Everything runs on source time until the final
    select, so captions stay on their measured word timings through every jump cut."""
    from .editor import balanced_sum
    from .transitions import visual_filters
    single = single_graph(info, settings, prepared)
    stacked = prepared.get('stacked') or []
    # zoompan numbers its output frames from 0; start_time=0 makes the input grid
    # start at 0 too, so every branch, caption and cut shares one timeline.
    head = f'fps={FPS}:round=up:start_time=0'
    if stacked:
        enable = balanced_sum([f'gte(t,{s["start"] - EPS:.4f})*lt(t,{s["end"] - EPS:.4f})' for s in stacked])
        vf = (f'{head},split=2[dv_si][dv_ki];[dv_si]{single}[dv_s];[dv_ki]{stacked_graph(info, stacked, prepared["end"] - prepared["start"])}[dv_k];'
              f"[dv_s][dv_k]overlay=0:0:shortest=1:enable='{enable}'")
    else:
        vf = f'{head},{single}'
    if settings.get('mix_seconds'):
        vf += ',' + visual_filters({'cuts': prepared['visual_cuts'], 'holds': []}, settings['mix_seconds'])
    if captions:
        escaped = str(captions).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
        vf += f",ass='{escaped}':fontsdir='{Path(__file__).parent / 'fonts'}'"
    if prepared.get('removed'):
        vf += ',' + select_filter(prepared['removed'], prepared['end'] - prepared['start'])
    return vf


def select_filter(removed, duration):
    from .editor import balanced_sum
    keep = balanced_sum([f'gte(t,{a - EPS:.4f})*lt(t,{b - EPS:.4f})' for a, b in kept_intervals(removed, duration)])
    return f"select='{keep}',setpts=N/{FPS}/TB"


def audio_filter(removed, duration):
    """Kept audio pieces with 8 ms fades at each join, so a jump cut never clicks."""
    if not removed:
        return 'aresample=48000,apad'
    kept = kept_intervals(removed, duration)
    labels = ''.join(f'[dir_a{i}]' for i in range(len(kept)))
    parts = [f'aresample=48000,asplit={len(kept)}{labels}' if len(kept) > 1 else 'aresample=48000,anull[dir_a0]']
    for i, (a, b) in enumerate(kept):
        fades = []
        if i > 0:
            fades.append('afade=t=in:st=0:d=0.008')
        if i < len(kept) - 1:
            fades.append(f'afade=t=out:st={max(0, b - a - .008):.4f}:d=0.008')
        parts.append(f"[dir_a{i}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS{''.join(',' + f for f in fades)}[dir_k{i}]")
    parts.append(''.join(f'[dir_k{i}]' for i in range(len(kept))) + f'concat=n={len(kept)}:v=0:a=1,apad')
    return ';'.join(parts)
