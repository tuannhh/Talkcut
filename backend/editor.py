"""Timeline composition and exact word-event subtitles at 1080 × 1920."""
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from . import config, google_ai, store
from .media import ffmpeg, probe, frame, encode_args, normalized_video

W, H = 1080, 1920


def font(size):
    for name in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/Library/Fonts/Arial Unicode.ttf'):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def wrap(text, f, width):
    lines, line = [], ''
    for word in text.split():
        candidate = f'{line} {word}'.strip()
        if f.getlength(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def asset(id, kind=None):
    if not id:
        return None
    item = store.get(id, 'asset')
    if kind and item['type'] != kind:
        raise ValueError(f'Tài nguyên phải là {kind}.')
    return config.DATA / item['path']


def draw_text_block(im, text, region, color='white', max_size=78, align='left'):
    x, y, width, height = region
    for size in range(max_size, 25, -2):
        f = font(size)
        lines = wrap(text, f, width)
        if len(lines) * size * 1.35 <= height:
            break
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        xx = x + (width - f.getlength(line)) / 2 if align == 'center' else x
        d.text((xx, y + i * size * 1.35), line, font=f, fill=color, stroke_width=0)


def summary_card(source, clip, target, settings):
    still = target.with_suffix('.jpg')
    frame(source, still, clip['start'])
    im = ImageOps.fit(Image.open(still).convert('RGB'), (W, H)).convert('RGBA')
    shade = Image.new('RGBA', (W, H))
    draw = ImageDraw.Draw(shade)
    for y in range(H):
        alpha = int(245 * min(1, max(0, (y / H - 0.32) / 0.30)))
        draw.line((0, y, W, y), fill=(16, 22, 18, alpha))
    im = Image.alpha_composite(im, shade)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((70, 1090, 77, 1490), radius=3, fill=settings['brand_color'])
    draw.text((106, 1050), 'ĐIỂM NHẤN CUỘC TRÒ CHUYỆN', font=font(27), fill=settings['brand_color'])
    draw_text_block(im, clip['summary'] or clip['title'], (106, 1125, 860, 465), max_size=70)
    im.save(target)


def fit_intro_regions(settings, title, exclusions):
    """Fit complete text rectangles in safe vertical bands outside detected logos."""
    blocked=[]
    for box in exclusions if isinstance(exclusions,list) else []:
        if not isinstance(box,list) or len(box)!=4:
            continue
        try:
            x1,y1,x2,y2=[float(v) for v in box]
        except (TypeError,ValueError):
            continue
        if not all(math.isfinite(v) for v in (x1,y1,x2,y2)) or not (0<=x1<x2<=1 and 0<=y1<y2<=1):
            continue
        if x2>.08 and x1<.92:
            blocked.append((max(.12,y1-.02),min(.83,y2+.02)))
    free=[];cursor=.12
    for a,b in sorted(blocked):
        if a>cursor:free.append((cursor,a))
        cursor=max(cursor,b)
    if cursor<.83:free.append((cursor,.83))
    free=[(a,b) for a,b in free if b-a>.08]
    if not free:
        raise ValueError('Nền có quá ít vùng trống cho hai lớp chữ. Hãy dùng nền khác hoặc đặt chữ thủ công.')
    if len(free)==1:
        a,b=free[0];middle=a+(b-a)*.62
        free=[(a,middle-.015),(middle+.015,b)]
    top,bottom=free[0],free[-1]
    changes={}
    for prefix,text,band in [('intro',settings['intro_text'],top),('intro_title',title.upper() if settings.get('intro_title_case')=='upper' else title,bottom)]:
        width=.84;size=settings[prefix+'_size'];a,b=band
        while size>=28:
            height=(len(wrap(text,font(size),int(width*W)-40))*size*1.35+40)/H
            if height<=b-a:break
            size-=2
        if size<28:
            raise ValueError('Nội dung quá dài cho vùng tránh logo. Hãy rút gọn lời mở đầu hoặc tiêu đề.')
        changes.update({prefix+'_x':.5,prefix+'_y':round((a+b)/2,3),prefix+'_width':width,prefix+'_size':size})
    return changes


def intro_card(settings, target, progress, title='', clip=None):
    if settings.get('intro_design') == 'photo' and clip:
        from .intro_art import photo_card
        return photo_card(settings, target, title, clip)
    """Two independently styled layers. Exact user positions survive rendering."""
    bg = asset(settings['intro_asset'], 'image')
    im = ImageOps.fit(Image.open(bg).convert('RGB'), (W, H)).convert('RGBA') if bg else Image.new('RGBA', (W, H), '#19211b')
    layouts = []
    for prefix, text in [('intro', settings['intro_text']), ('intro_title', title if settings.get('intro_title_enabled', True) else '')]:
        if not text.strip():
            continue
        if prefix == 'intro_title' and settings.get('intro_title_case') == 'upper':
            text = text.upper()
        size = settings[prefix + '_size']
        width = int(settings[prefix + '_width'] * W)
        max_height = H * (.43 if prefix == 'intro' else .28)
        while True:
            f = font(size)
            lines = wrap(text, f, width - 40)
            height = int(len(lines) * size * 1.35 + 40)
            if height <= max_height or size <= 26:
                break
            size -= 2
        if height > H - 50:
            raise ValueError('Chữ intro quá dài cho khung hình. Hãy rút gọn lời mở đầu.')
        x = max(25, min(W - width - 25, int(settings[prefix + '_x'] * W - width / 2)))
        y = max(25, min(H - height - 25, int(settings[prefix + '_y'] * H - height / 2)))
        layouts.append({'prefix': prefix, 'x': x/W, 'y': y/H, 'width': width/W, 'height': height/H, 'size': size})
        color = settings[prefix + '_color']
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        light = sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722))) > 140
        layer = Image.new('RGBA', (W,H))
        ImageDraw.Draw(layer).rounded_rectangle((x,y,x+width,y+height), radius=18, fill=(8,15,12,220) if light else (255,255,255,225))
        im = Image.alpha_composite(im, layer)
        d = ImageDraw.Draw(im)
        for i,line in enumerate(lines):
            d.text((x + (width-f.getlength(line))/2,y+20+i*size*1.35),line,font=f,fill=color)
    im.save(target)
    return layouts


def ass_time(seconds):
    ticks = max(0, round(seconds * 100))
    return f'{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}'


def ass_escape(text):
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', ' ')


def subtitle_groups(words, count):
    groups, group = [], []
    for word in words:
        if group and (len(group) >= count or group[-1]['text'].rstrip('”"' + chr(39)).endswith(('.', '!', '?', '…')) or word['start'] - group[-1]['end'] > .7 or word.get('speaker') != group[-1].get('speaker')):
            groups.append(group)
            group = []
        group.append(word)
    if group:
        groups.append(group)
    return groups


def make_ass(words, clip, settings, target):
    selected = [{**w, 'start': max(0, w['start'] - clip['start']), 'end': min(clip['end'], w['end']) - clip['start']} for w in words if w['end'] > clip['start'] and w['start'] < clip['end']]
    color = settings['caption_color'].lstrip('#')
    color = color[4:6] + color[2:4] + color[:2]
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', 'WrapStyle: 0',
             '[V4+ Styles]', 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             f'Style: Default,DejaVu Sans,{settings["caption_size"]},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,5,85,140,0,1',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    for group in subtitle_groups(selected, settings['caption_words']):
        # One event per spoken word, plus neutral gaps. No proportional timing guesses.
        boundaries = sorted({w['start'] for w in group} | {w['end'] for w in group})
        for start, end in zip(boundaries, boundaries[1:]):
            if end <= start:
                continue
            texts = []
            for word in group:
                active = word['start'] <= (start + end) / 2 < word['end']
                texts.append('{\\c&H' + (color if active else 'FFFFFF') + '&}' + ass_escape(word['text']))
            body = '{\\an5\\pos(' + str(round(settings.get('caption_x',510/1080)*W)) + ',' + str(round(settings['caption_y'] * H)) + ')}' + ' '.join(texts)
            lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{body}')
    target.write_text('\n'.join(lines), encoding='utf-8')


def validate_track(raw, duration):
    result = []
    for p in raw:
        t, x = float(p['time']), float(p['x'])
        if math.isfinite(t) and math.isfinite(x) and 0 <= t <= duration and 0 <= x <= 1:
            result.append({'time': round(t, 3), 'x': x})
    return sorted({p['time']: p for p in result}.values(), key=lambda p: p['time'])[:180]


def focus_track(source, clip, directory, progress, words=None):
    from .focus import analyze
    return analyze(source, clip, progress, words)


def balanced_sum(terms):
    # FFmpeg limits expression tree depth. Long clips need a balanced tree,
    # preserving every tracking sample instead of dropping camera movements.
    if not terms:
        return '0'
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return '(' + balanced_sum(terms[:middle]) + '+' + balanced_sum(terms[middle:]) + ')'


def crop_filter(info, settings, track=None):
    fit = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1'
    if settings['crop_mode'] == 'fit':
        return fit
    iw, ih = info['width'], info['height']
    zoom = settings.get('crop_zoom', 1)
    cw = int(min(iw, ih * 9 / 16) / zoom) // 2 * 2
    ch = int(min(ih, iw * 16 / 9) / zoom) // 2 * 2
    center = settings['crop_x'] if settings['crop_mode'] == 'manual' else .5
    xexpr = str(max(0, min(iw-cw, iw*center-cw/2)))
    yexpr = str((ih-ch)//2)
    fit_intervals=[]
    if track:
        from .focus import prepared_track
        track = prepared_track(track, info, settings)
        points = track['keyframes']
        def expression(axis, full, extent):
            values=[max(0,min(full-extent,p.get(axis,.5)*full-extent/2)) for p in points]
            terms=[str(round(values[0],2))]
            for i in range(len(points)-1):
                p,q=points[i:i+2]
                change=values[i+1]-values[i]
                if abs(change)<.001:continue
                a,b=p['time'],q['time']
                jump=q.get('cut') or p.get('scene')!=q.get('scene') or p.get('mode')!=q.get('mode') or abs(change)>full*.18
                terms.append(f'({change:.2f})*gte(t,{b})' if jump else f'({change:.2f})*clip((t-{a})/{max(.01,b-a)},0,1)')
            return balanced_sum(terms)
        if points:
            xexpr=expression('x',iw,cw)
            yexpr=expression('y',ih,ch)
        for i,p in enumerate(points):
            if p.get('mode')=='fit':
                end=points[i+1]['time'] if i+1<len(points) else track.get('end',0)-track.get('start',0)
                if fit_intervals and abs(fit_intervals[-1][1]-p['time'])<.01:fit_intervals[-1][1]=end
                else:fit_intervals.append([p['time'],end])
    portrait=f"crop={cw}:{ch}:x='{xexpr}':y='{yexpr}',scale=1080:1920:flags=lanczos,setsar=1"
    if fit_intervals:
        enable=balanced_sum([f'gte(t,{a})*lt(t,{b})' for a,b in fit_intervals])
        return f"split[fc][fw];[fc]{portrait}[tight];[fw]{fit}[wide];[tight][wide]overlay=0:0:enable='{enable}'"
    return portrait


def still_segment(image, target, seconds, audio=None, captions=None):
    args = ['-loop', '1', '-framerate', '30', '-i', image]
    args += ['-i', audio] if audio else ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    if captions:
        escaped=str(captions).replace('\\','\\\\').replace(':','\\:').replace("'","'\\''")
        args += ['-vf', f"ass='{escaped}'"]
    ffmpeg([*args, '-map', '0:v', '-map', '1:a', '-af', 'apad', '-t', str(seconds), *encode_args(), target])


def watermark_image(settings, target):
    im = Image.new('RGBA', (W, H))
    width = round(W * settings['watermark_scale'])
    if settings['watermark_kind'] == 'image':
        path = asset(settings['watermark_asset'], 'image')
        if not path:
            raise ValueError('Hãy upload ảnh watermark.')
        mark = Image.open(path).convert('RGBA')
        mark = ImageOps.contain(mark, (width, H // 3), Image.Resampling.LANCZOS)
    else:
        text = settings['watermark_text']
        f = font(60)
        box = f.getbbox(text or ' ')
        mark = Image.new('RGBA', (max(1, box[2] + 8), max(1, box[3] - box[1] + 12)))
        ImageDraw.Draw(mark).text((4, 4 - box[1]), text, font=f, fill='white', stroke_width=1, stroke_fill='#222222')
        mark = mark.resize((width, max(1, round(mark.height * width / mark.width))))
    alpha = mark.getchannel('A').point(lambda v: round(v * settings['watermark_opacity']))
    mark.putalpha(alpha)
    x = max(0, min(W - mark.width, round(settings['watermark_x'] * W - mark.width / 2)))
    y = max(0, min(H - mark.height, round(settings['watermark_y'] * H - mark.height / 2)))
    im.alpha_composite(mark, (x, y))
    im.save(target)


def render(source, clip, words, settings, directory, progress):
    from .schemas import Settings
    settings = Settings.model_validate(settings).model_dump()
    directory.mkdir(exist_ok=True, parents=True)
    parts = []
    if settings['summary_enabled']:
        progress('Đang dựng thẻ tóm tắt', 10)
        summary_card(source, clip, directory / 'summary.png', settings)
        still_segment(directory / 'summary.png', directory / 'summary.mp4', settings['summary_seconds'])
        parts.append(directory / 'summary.mp4')
    if settings['intro_enabled']:
        if settings['intro_tts'] and not settings['intro_text'].strip():
            raise ValueError('Hãy nhập lời mở đầu hoặc tắt đọc lời mở đầu.')
        intro_card(settings, directory / 'intro.png', progress, clip['title'], clip)
        audio, seconds = None, settings['intro_seconds']
        if settings['intro_tts']:
            progress('Google TTS đang thu voice off', 23)
            from .narration import synthesize
            audio, voice_plan = synthesize(settings['intro_text'], settings['intro_voice'], settings.get('intro_approval_id'), settings['intro_voice_mode'], settings['intro_voice_profile'])
            import json
            (directory / 'normalization.json').write_text(json.dumps(voice_plan, ensure_ascii=False))
            seconds = probe(audio)['duration'] + .35
        if audio and settings['intro_caption_enabled']:
            from .narration import align_display
            intro_words = align_display(audio, settings['intro_text'])
            make_ass(intro_words, {'start':0,'end':seconds}, {**settings,'caption_y':settings['intro_caption_y'],'caption_x':settings['intro_caption_x']}, directory/'intro.ass')
            still_segment(directory/'intro.png', directory/'intro.mp4', seconds, audio, directory/'intro.ass')
        else:
            still_segment(directory / 'intro.png', directory / 'intro.mp4', seconds, audio)
        parts.append(directory / 'intro.mp4')
    info = probe(source)
    track = focus_track(source, clip, directory, progress, words) if settings['crop_mode'] == 'auto' and (info['width'] / info['height'] > .57 or settings.get('crop_zoom', 1) > 1) else None
    vf = crop_filter(info, settings, track)
    from .transitions import transition_plan,visual_filters
    pacing=transition_plan(track,info,settings)
    vf += ','+visual_filters(pacing,settings.get('mix_seconds',.24))
    if settings['caption_enabled']:
        if not words:
            raise ValueError('Chưa có transcript. Phân tích nguồn trước hoặc tắt phụ đề.')
        make_ass(words, clip, settings, directory / 'captions.ass')
        # Generated UUID-only paths under DATA; no user text enters filter syntax.
        escaped = str(directory / 'captions.ass').replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
        vf += f",ass='{escaped}'"
    progress('Đang dựng nội dung và phụ đề karaoke Full HD', 42)
    ffmpeg(['-ss', str(clip['start']), '-i', source, '-t', str(clip['end'] - clip['start']), '-vf', vf,
            '-af', 'aresample=48000,apad', *encode_args(), directory / 'main.mp4'])
    parts.append(directory / 'main.mp4')
    if settings['outro_asset']:
        progress('Đang ghép outro', 65)
        normalized_video(asset(settings['outro_asset'], 'video'), directory / 'outro.mp4')
        parts.append(directory / 'outro.mp4')
    playlist = directory / 'concat.txt'
    playlist.write_text('\n'.join("file '" + p.name + "'" for p in parts))
    joined = directory / 'joined.mp4'
    ffmpeg(['-f', 'concat', '-safe', '0', '-i', playlist, '-c', 'copy', joined])
    progress('Đang trộn nhạc và áp dụng watermark', 78)
    output = directory / 'final.mp4'
    args = ['-i', joined]
    filters, v, a, index = [], '0:v', '0:a', 1
    if settings['watermark_kind'] != 'none':
        watermark_image(settings, directory / 'watermark.png')
        args += ['-i', directory / 'watermark.png']
        filters.append(f'[0:v][{index}:v]overlay=0:0[vout]')
        v = '[vout]'
        index += 1
    if settings['music_asset']:
        args += ['-stream_loop', '-1', '-i', asset(settings['music_asset'], 'audio')]
        filters += [f'[{index}:a]volume={settings["music_volume"]},aresample=48000[bg]',
                    '[0:a]asplit=2[voice][side]', '[bg][side]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=500[duck]',
                    '[voice][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]']
        a = '[aout]'
    if filters:
        args += ['-filter_complex', ';'.join(filters), '-map', v, '-map', a, '-t', str(probe(joined)['duration']), *encode_args(), output]
        ffmpeg(args)
    else:
        import shutil
        shutil.copyfile(joined, output)
    progress('Đang kiểm tra file xuất', 96)
    result = probe(output)
    if result.get('width') != W or result.get('height') != H or not result['has_audio']:
        raise ValueError('File xuất không đạt cấu hình Full HD có âm thanh.')
    return output, result, track
