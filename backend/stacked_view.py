"""AI-chosen wide two-person shots become a stacked two-frame composite.

Two user-selected subjects keep a fixed position (top/bottom) for the whole
clip, matching the reference split-screen format this feature was built from.
Detection never guesses who is speaking: it only checks that both selected
appearances are simultaneously, confidently visible in a wide enough camera
shot. Shots that do not clear that bar keep the ordinary single-subject crop.
"""
import hashlib
import json
import math
import statistics
import threading
from pathlib import Path
from . import config
from .media import ffmpeg, hwaccel_input_args

_lock = threading.RLock()
VERSION = 'stacked-v2'
SEAM_HEIGHT = 300
SEAM_BLUR = 40


def wide_two_shot(box_top, box_bottom, max_width=.40, min_gap=.035):
    """A wide/full camera shot showing both selected people, not a close-up.

    Face width is a proxy for shot size: a close-up single-person crop keeps
    a large face, while a wide two-person shot keeps both faces small and
    horizontally separated. This never decides who is speaking.
    """
    if not box_top or not box_bottom:
        return False
    try:
        ax1, ay1, ax2, ay2 = [float(v) for v in box_top]
        bx1, by1, bx2, by2 = [float(v) for v in box_bottom]
    except (TypeError, ValueError):
        return False
    if not (math.isfinite(ax1) and math.isfinite(bx1)):
        return False
    if (ax2 - ax1) > max_width or (bx2 - bx1) > max_width:
        return False
    left, right = (ax1, ax2), (bx1, bx2)
    if left[0] > right[0]:
        left, right = right, left
    return right[0] - left[1] >= min_gap


def half_geometry(info, settings, face):
    """A tight bust crop for one half of the stacked canvas (9:8 tile)."""
    iw, ih = info['width'], info['height']
    zoom = min(2, settings.get('crop_zoom', 1) * 1.45)
    cw = max(2, int(min(iw, ih * 9 / 16) / zoom) // 2 * 2)
    ch = max(2, int(cw * 8 / 9) // 2 * 2)
    x1, y1, x2, y2 = face
    fw, fh = x2 - x1, y2 - y1
    left, right = max(0, x1 - fw * .15), min(1, x2 + fw * .15)
    top, bottom = max(0, y1 - fh * .45), min(1, y2 + fh * .9)
    if (right - left) * iw > cw or (bottom - top) * ih > ch:
        cx = max(cw / iw / 2, min(1 - cw / iw / 2, (x1 + x2) / 2))
        cy = max(ch / ih / 2, min(1 - ch / ih / 2, (y1 + y2) / 2))
    else:
        cx = max(right - cw / iw / 2, min(left + cw / iw / 2, (x1 + x2) / 2))
        cy = max(bottom - ch / ih / 2, min(top + ch / ih / 2, (y1 + y2) / 2 + ch / ih * .12))
    x = max(0, min(iw - cw, cx * iw - cw / 2))
    y = max(0, min(ih - ch, cy * ih - ch / 2))
    return {'x': (x + cw / 2) / iw, 'y': (y + ch / 2) / ih, 'cw': cw, 'ch': ch}


def median_box(boxes):
    return [statistics.median(b[i] for b in boxes) for i in range(4)]


def assemble(samples, cuts, clip, token_top, token_bottom, min_duration=.8):
    """One representative box per qualifying shot; a locked crop, not a jitter track."""
    duration = clip['end'] - clip['start']
    bounds = [0, *cuts, duration]
    segments = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < min_duration:
            continue
        group = [s for s in samples if a <= s['time'] < b]
        if not group:
            continue
        qualifying = [s for s in group if wide_two_shot(s.get('top'), s.get('bottom'))]
        if len(qualifying) < max(1, math.ceil(len(group) * .5)):
            continue
        segments.append({
            'start': a, 'end': b, 'top': token_top, 'bottom': token_bottom,
            'box_top': median_box([s['top'] for s in qualifying]),
            'box_bottom': median_box([s['bottom'] for s in qualifying]),
        })
    return {
        'version': VERSION, 'start': clip['start'], 'end': clip['end'], 'segments': segments,
        'note': f'{len(segments)} đoạn cảnh toàn đủ chắc chắn cả hai chủ thể để ghép khung; các đoạn khác giữ khung đơn bình thường.',
    }


def cache_dir(source, clip, token_top, token_bottom):
    stat = Path(source).stat()
    identity = [VERSION, str(source), stat.st_size, stat.st_mtime_ns, clip['start'], clip['end'], token_top, token_bottom]
    key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
    return config.DATA / 'jobs' / ('stacked-' + key)


def detect(source, clip, progress=lambda *a: None):
    """Cached: returns the previous result without recomputing when unchanged."""
    from . import focus
    from .subject_tracking import reference
    from .face_engine import describe, portrait, best_match
    settings = clip.get('settings', {})
    token_top, token_bottom = settings.get('tracking_subject'), settings.get('tracking_subject_2')
    if not token_top or not token_bottom:
        raise ValueError('Hãy chọn cả hai chủ thể (trên và dưới) trước khi ghép khung.')
    directory = cache_dir(source, clip, token_top, token_bottom)
    cache = directory / 'stacked.json'
    with _lock:
        if cache.exists():
            return json.loads(cache.read_text())
        directory.mkdir(parents=True, exist_ok=True)
        import cv2
        ref_top, ref_bottom = reference(source, token_top), reference(source, token_bottom)
        face_top = portrait(describe(cv2.imread(str(config.DATA / ref_top['path']))))
        face_bottom = portrait(describe(cv2.imread(str(config.DATA / ref_bottom['path']))))
        if not face_top or not face_bottom:
            raise ValueError('Chưa thấy rõ khuôn mặt của một trong hai chủ thể đã chọn. Chọn lại ảnh khác.')
        embedding_top, embedding_bottom = face_top['embedding'], face_bottom['embedding']
        duration = clip['end'] - clip['start']
        base = focus.cache_dir(source, {**clip, 'settings': {}})
        for i, a in enumerate(range(0, math.ceil(duration), 30)):
            proxy = directory / f'shots-{i}.mp4'
            old = base / proxy.name
            if not proxy.exists():
                if old.exists():
                    import shutil
                    shutil.copyfile(old, proxy)
                else:
                    ffmpeg(['-ss', str(clip['start'] + a), *hwaccel_input_args(), '-i', source, '-t', str(min(30, duration - a)),
                            '-vf', 'scale=720:-2,fps=6', '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '24', proxy])
        progress('Đang tách góc máy để tìm cảnh toàn đủ hai người', 15)
        layout = {}
        focus.visual_layout(directory, layout, source, clip)
        cuts = layout.get('visual_cuts', [])
        bounds = [0, *cuts, duration]
        samples, caps = [], {}
        try:
            for shot, (a, b) in enumerate(zip(bounds, bounds[1:])):
                count = max(1, min(8, math.ceil((b - a) / 3)))
                for j in range(count):
                    t = a + (b - a) * (j + .5) / count
                    i = int(t // 30)
                    if i not in caps:
                        caps[i] = cv2.VideoCapture(str(directory / f'shots-{i}.mp4'))
                    cap = caps[i]
                    cap.set(cv2.CAP_PROP_POS_MSEC, (t - i * 30) * 1000)
                    ok, img = cap.read()
                    if not ok:
                        continue
                    ident = len(samples)
                    path = directory / f'sample-{ident}.jpg'
                    cv2.imwrite(str(path), img)
                    samples.append({'id': ident, 'shot': shot, 'time': round(t, 5), 'path': str(path)})
        finally:
            for c in caps.values():
                c.release()
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def match_sample(sample):
            image = cv2.imread(sample['path'])
            faces = describe(image) if image is not None else []
            top_match = best_match(embedding_top, faces)
            remaining = [f for f in faces if f is not top_match]
            bottom_match = best_match(embedding_bottom, remaining)
            return {**sample, 'top': top_match['box'] if top_match else None, 'bottom': bottom_match['box'] if bottom_match else None}

        prepared = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(match_sample, s) for s in samples]
            for index, future in enumerate(as_completed(futures), 1):
                prepared.append(future.result())
                if index == len(samples) or index % 4 == 0:
                    progress(f'Đang tìm cảnh có đủ hai chủ thể · {index}/{max(1,len(samples))}', 20 + int(index / max(1, len(samples)) * 70))
        samples = sorted(prepared, key=lambda s: s['id'])
        result = assemble(samples, cuts, clip, token_top, token_bottom)
        temp = directory / 'stacked.tmp'
        temp.write_text(json.dumps(result, ensure_ascii=False))
        temp.replace(cache)
        progress(f'Đã tìm thấy {len(result["segments"])} đoạn ghép khung', 95)
        return result


def seam_mask_asset():
    """Shape only, no colour: a vertical alpha fade used to blend the seam.

    The seam itself takes its colour from the clip's own footage (a blurred
    bridge between the two crops), so it matches any background/lighting
    instead of imposing a fixed black/white band. This mask just controls how
    that blurred bridge fades into the sharp crops above and below it.
    """
    # v2: a fully-opaque central plateau (the hard vstack boundary sits here
    # and must be completely hidden by the blurred bridge) that only fades to
    # transparent near the top/bottom edges. The earlier version peaked at 235
    # and fell off immediately from the centre, leaving the seam visible.
    path = config.DATA / 'generated' / 'stacked-seam-mask-v2.png'
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw
    im = Image.new('L', (1080, SEAM_HEIGHT), 0)
    draw = ImageDraw.Draw(im)
    plateau = 0.5  # central 50% stays fully opaque; only the outer 25% each side fades
    for y in range(SEAM_HEIGHT):
        distance = abs(y - SEAM_HEIGHT / 2) / (SEAM_HEIGHT / 2)
        if distance <= plateau:
            value = 255
        else:
            edge = (distance - plateau) / (1 - plateau)  # 0 at plateau boundary -> 1 at the very edge
            value = int(255 * max(0, 1 - edge) ** 1.6)
        draw.line((0, y, 1080, y), fill=value)
    im.save(path)
    return path


def wrap(vf, segments, info, settings):
    """Overlay a stacked composite onto the existing filter graph during AI-chosen windows.

    The existing graph (crop/mix/etc, built for the primary subject) runs
    unchanged on one branch; a second branch crops the two selected faces
    directly from the original frame and stacks them. The seam between them
    is a heavily blurred bridge built from the stacked image's own pixels
    (not a fixed colour), so it always matches this clip's actual background
    and lighting; a static alpha mask only controls how it fades into the
    sharp crops above and below. Only shown during the detected windows.
    Audio and caption timing are untouched: this is a purely visual overlay,
    like the existing Mix.
    """
    if not segments:
        return vf
    from .editor import balanced_sum
    iw, ih = info['width'], info['height']
    tops = [half_geometry(info, settings, s['box_top']) for s in segments]
    bottoms = [half_geometry(info, settings, s['box_bottom']) for s in segments]
    cw, ch = tops[0]['cw'], tops[0]['ch']

    def offsets(geoms, axis):
        full, extent = (iw, cw) if axis == 'x' else (ih, ch)
        return [max(0, min(full - extent, g[axis] * full - extent / 2)) for g in geoms]

    def expression(geoms, axis):
        offs = offsets(geoms, axis)
        terms = [str(round(offs[0], 2))]
        for i in range(len(segments) - 1):
            change = offs[i + 1] - offs[i]
            if abs(change) < .5:
                continue
            terms.append(f'({change:.2f})*gte(t,{segments[i + 1]["start"]})')
        return balanced_sum(terms)

    top_x, top_y = expression(tops, 'x'), expression(tops, 'y')
    bottom_x, bottom_y = expression(bottoms, 'x'), expression(bottoms, 'y')
    enable = balanced_sum([f'gte(t,{s["start"]})*lt(t,{s["end"]})' for s in segments])
    mask = str(seam_mask_asset()).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
    seam_y = 960 - SEAM_HEIGHT // 2
    return (
        f"split=2[sv_src][sv_pipein];"
        f"[sv_pipein]{vf}[sv_pipeout];"
        f"[sv_src]split=2[sv_topin][sv_botin];"
        f"[sv_topin]crop={cw}:{ch}:x='{top_x}':y='{top_y}',scale=1080:960:flags=lanczos,setsar=1[sv_top];"
        f"[sv_botin]crop={cw}:{ch}:x='{bottom_x}':y='{bottom_y}',scale=1080:960:flags=lanczos,setsar=1[sv_bot];"
        f"[sv_top][sv_bot]vstack=inputs=2[sv_stacked];"
        f"[sv_stacked]split=2[sv_base][sv_seamsrc];"
        f"[sv_seamsrc]crop=1080:{SEAM_HEIGHT}:0:{seam_y},boxblur={SEAM_BLUR}:{SEAM_BLUR}[sv_blur];"
        f"movie='{mask}',loop=loop=-1:size=1:start=0,setpts=N/30/TB,format=gray[sv_mask];"
        f"[sv_blur][sv_mask]alphamerge[sv_seam];"
        f"[sv_base][sv_seam]overlay=0:{seam_y}[sv_final];"
        f"[sv_pipeout][sv_final]overlay=0:0:enable='{enable}'"
    )
