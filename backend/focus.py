"""Audio-aware shot planning. Portrait framing never interrupts the source speech.

The same versioned plan is used in the browser and FFmpeg; face detection refines
geometry only and never decides who is speaking.
"""
import hashlib
import json
import math
import threading
_layout_lock=threading.RLock()
from pathlib import Path
from . import config, google_ai
from .media import ffmpeg, hwaccel_input_args

VERSION = 'speaker-shots-v2.2'
MAX_HOLD_SECONDS = 1.6
KINDS = {'speaker', 'reaction', 'broll', 'wrong_shot', 'broken', 'transition', 'end', 'uncertain'}
LABELS = {'selected':'Chủ thể đã chọn','speaker': 'Người đang nói', 'reaction': 'Cảnh người nghe', 'broll': 'Cảnh trám', 'wrong_shot': 'Có thể quay nhầm', 'broken': 'Hình lỗi / mất nét', 'transition': 'Chuyển cảnh / lia máy', 'end': 'Kết cảnh', 'uncertain': 'Chưa đủ bằng chứng'}


def cache_dir(source, clip):
    stat = Path(source).stat()
    identity = [VERSION, str(source), stat.st_size, stat.st_mtime_ns, clip['start'], clip['end'], config.CONTENT_MODEL]
    if clip.get('settings',{}).get('tracking_subject'):
        from .subject_tracking import VERSION as reference_version
        identity += [reference_version,clip['settings']['tracking_subject']]
    key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
    return config.DATA / 'jobs' / ('focus-' + key)


def cached(source, clip):
    with _layout_lock:return _cached(source,clip)


def _cached(source, clip):
    path = cache_dir(source, clip) / 'focus.json'
    if not path.exists(): return None
    result=json.loads(path.read_text())
    if result.get('reference_tracking'):return result
    changed=False
    if result.get('layout_version')!='portrait-v5.1':
        enrich_reactions(path.parent,result)
        visual_layout(path.parent,result,source,clip)
        changed=True
    if result.get('geometry_version')!='face-v6':
        from .face_tracking import refresh_geometry
        refresh_geometry(path.parent,result)
        changed=True
    if changed:
        import uuid
        temp=path.with_name(uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(result,ensure_ascii=False));temp.replace(path)
    return result


def number(value, default=0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


def sanitize(raw, duration):
    """Fill gaps conservatively; unsafe or incomplete model output cannot crop."""
    if not isinstance(raw, list):
        raw = []
    scenes, cursor = [], 0
    for row in sorted((r for r in raw if isinstance(r, dict)), key=lambda r: number(r.get('start'))):
        start = max(cursor, min(duration, number(row.get('start'))))
        end = max(start, min(duration, number(row.get('end'))))
        if end <= start:
            continue
        if start > cursor + .02:
            scenes.append({'start': cursor, 'end': start, 'kind': 'uncertain', 'confidence': 0, 'speaker': '', 'reason': 'Chưa có dữ liệu cho khoảng này.', 'keyframes': []})
        kind = row.get('kind') if row.get('kind') in KINDS else 'uncertain'
        confidence = max(0, min(1, number(row.get('confidence'))))
        points = []
        keyframes = row.get('keyframes') or []
        for p in (keyframes if isinstance(keyframes, list) else [])[:240]:
            if not isinstance(p, dict):
                continue
            box = p.get('face', [])
            if not isinstance(box, list) or len(box) != 4:
                continue
            x1, y1, x2, y2 = [number(v, -1) for v in box]
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                continue
            points.append({'time': max(start, min(end, number(p.get('time'), start))), 'x': (x1+x2)/2, 'face': [x1,y1,x2,y2]})
        points = sorted({p['time']: p for p in points}.values(), key=lambda p: p['time'])
        if kind == 'speaker' and (confidence < .75 or not points or not row.get('visible_speaking')):
            kind = 'uncertain'
        scenes.append({'start': start, 'end': end, 'kind': kind, 'confidence': confidence, 'speaker': str(row.get('speaker', ''))[:80], 'reason': str(row.get('reason', ''))[:350], 'keyframes': points})
        cursor = end
    if cursor < duration:
        scenes.append({'start': cursor, 'end': duration, 'kind': 'uncertain', 'confidence': 0, 'speaker': '', 'reason': 'Chưa xác định được cảnh.', 'keyframes': []})
    return scenes


def geometry(info, settings, p):
    """Portrait window with face/headroom constraints; only explicit fit letterboxes."""
    iw, ih = info['width'], info['height']
    zoom = settings.get('crop_zoom', 1)
    cw = max(2, int(min(iw, ih*9/16)/zoom)//2*2)
    ch = max(2, int(min(ih, iw*16/9)/zoom)//2*2)
    if settings.get('crop_mode') == 'fit':
        return {'mode':'fit', 'x':.5, 'y':.5, 'cw':cw, 'ch':ch}
    face = p.get('face')
    cx = p.get('x', .5)
    cy = p.get('y',.5)
    if face:
        x1,y1,x2,y2 = face
        fw,fh = x2-x1,y2-y1
        # Include hair, chin and a margin; never choose the center of a table.
        left,right = max(0,x1-fw*.15),min(1,x2+fw*.15)
        top,bottom = max(0,y1-fh*.5),min(1,y2+fh*.3)
        if (right-left)*iw > cw or (bottom-top)*ih > ch:
            return {'mode':'crop','x':max(cw/iw/2,min(1-cw/iw/2,(x1+x2)/2)),'y':max(ch/ih/2,min(1-ch/ih/2,(y1+y2)/2)),'cw':cw,'ch':ch}
        cx = max(right-cw/iw/2, min(left+cw/iw/2,cx))
        # Eyes near upper third when zoomed; preserve the original vertical view otherwise.
        cy = max(bottom-ch/ih/2, min(top+ch/ih/2, (y1+y2)/2+ch/ih*.17))
    x = max(0,min(iw-cw,cx*iw-cw/2))
    y = max(0,min(ih-ch,cy*ih-ch/2))
    return {'mode':'crop','x':(x+cw/2)/iw,'y':(y+ch/2)/ih,'cw':cw,'ch':ch}


def refine(proxy, scenes):
    import cv2
    cap = cv2.VideoCapture(str(proxy))
    fps = cap.get(cv2.CAP_PROP_FPS) or 6
    detector = cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    # Locate visual cuts at proxy-frame precision, then snap nearby model boundaries.
    cuts=[];previous=None;frame_index=0
    while True:
        ok,img=cap.read()
        if not ok:break
        tiny=cv2.resize(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(64,36))
        if previous is not None and float(cv2.absdiff(tiny,previous).mean())>24:
            cuts.append(frame_index/fps)
        previous=tiny;frame_index+=1
    cap.set(cv2.CAP_PROP_POS_FRAMES,0)
    for i in range(1,len(scenes)):
        nearby=[t for t in cuts if abs(t-scenes[i]['start'])<.8 and scenes[i-1]['start']<t<scenes[i]['end']]
        if nearby:
            cut=min(nearby,key=lambda t:abs(t-scenes[i]['start']))
            scenes[i-1]['end']=cut;scenes[i]['start']=cut
    points, index, current = [], 0, 0
    previous_gray = None
    while True:
        ok,img = cap.read()
        if not ok:
            break
        t=index/fps; index+=1
        # Half-second geometry samples; shot boundaries inserted separately below.
        if (index-1) % max(1, round(fps/2)):
            continue
        while current+1<len(scenes) and scenes[current]['end']<=t:
            current+=1
        scene=scenes[current]
        gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        tiny=cv2.resize(gray,(64,36))
        changed = previous_gray is not None and float(cv2.absdiff(tiny,previous_gray).mean())>24
        previous_gray=tiny
        p={'time':round(t,3),'x':.5,'mode':'fit','cut':changed,'scene':current,'kind':scene['kind'],'speaker':scene['speaker']}
        if scene['kind']=='speaker':
            anchors=scene['keyframes']
            anchor=min(anchors,key=lambda a:abs(a['time']-t))
            p.update(x=anchor['x'],face=anchor['face'],mode='crop')
            detected=detector.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(24,24))
            candidates=[f for f in detected if abs((f[0]+f[2]/2)/img.shape[1]-anchor['x'])<.14]
            if candidates:
                f=min(candidates,key=lambda f:abs((f[0]+f[2]/2)/img.shape[1]-anchor['x']))
                x,y,w,h=[float(v) for v in f]
                p['face']=[x/img.shape[1],y/img.shape[0],(x+w)/img.shape[1],(y+h)/img.shape[0]]
                p['x']=(x+w/2)/img.shape[1]
            elif changed and not any(abs(t-s['start'])<=.55 for s in scenes):
                # Unexpected visual cuts abstain; brief profile-face detection misses
                # within an established shot keep the audio-verified subject stable.
                p['mode']='fit'
        points.append(p)
    cap.release()
    for i,s in enumerate(scenes):
        p={'time':s['start'],'x':.5,'mode':'fit','cut':True,'scene':i,'kind':s['kind'],'speaker':s['speaker']}
        if s['kind']=='speaker':
            p.update(s['keyframes'][0],time=s['start'],mode='crop')
        points.append(p)
    return sorted({p['time']:p for p in points}.values(),key=lambda p:p['time'])


def analyze(source, clip, progress, words=None):
    directory=cache_dir(source,clip); directory.mkdir(parents=True,exist_ok=True)
    found=cached(source,clip)
    if found:
        return found
    if clip.get('settings',{}).get('tracking_subject'):
        from .subject_tracking import analyze as reference_analyze
        return reference_analyze(source,clip,progress)
    duration=clip['end']-clip['start']
    scenes=[]
    # Small windows keep lip motion visible and make chunk retries reusable.
    for index, start in enumerate(range(0,math.ceil(duration),30)):
        length=min(30,duration-start)
        progress(f'Đang xác định người nói và loại cảnh · {index+1}/{math.ceil(duration/30)}', 10+int(start/duration*75))
        part=directory/f'shots-{index}.json'
        proxy=directory/f'shots-{index}.mp4'
        if part.exists():
            chunk=json.loads(part.read_text())
        else:
            ffmpeg(['-ss',str(clip['start']+start),*hwaccel_input_args(),'-i',source,'-t',str(length),'-vf','scale=720:-2,fps=6','-c:v','libx264','-preset','ultrafast','-crf','24','-c:a','aac','-b:a','64k',proxy])
            excerpt=[{'time':round(w['start']-clip['start']-start,2),'text':w['text'],'speaker':w.get('speaker','')} for w in (words or []) if clip['start']+start<=w['start']<clip['start']+start+length]
            prompt='''Bạn là đạo diễn dựng video toạ đàm. PHẢI nghe audio và quan sát chuyển động môi để xác định người ĐANG NÓI, không chọn người to nhất/ở giữa/người đang nghe. Transcript chỉ là gợi ý; nhãn speaker không phải danh tính.
Chia toàn bộ video đính kèm thành các cảnh liên tiếp; tách cảnh tại mỗi cut, đổi người nói, bắt đầu/kết thúc lia máy. Thời gian GIÂY tính từ 0 của file đính kèm.
Phân loại kind: speaker (người đang nói thấy rõ, môi khớp tiếng); reaction (cảnh người nghe khi người khác tiếp tục nói); broll (cảnh trám có chủ ý); wrong_shot (có dấu hiệu quay nhầm, không kết luận chắc nếu thiếu bằng chứng); broken (đen/mất tín hiệu/mất nét nặng); transition (lia máy/cut); end (hết cảnh/hết chương trình); uncertain.
Camera lia sang người khác không có nghĩa lời thoại kết thúc. Không cắt hoặc bỏ audio. Không giả định người xuất hiện đang nói. Nếu người nói ngoài khung, nhiều người cùng nói hoặc môi không rõ: visible_speaking=false và confidence thấp. Chỉ speaker rõ ràng mới được crop; các cảnh khác giữ toàn khung.
Trong từng cảnh speaker trả bbox MẶT của đúng người nói [x1,y1,x2,y2] tỷ lệ 0..1 (không phải cropbox), keyframes mỗi 1 giây và khi vị trí đổi. Bao gồm điểm ở đầu cảnh. Người quay nghiêng vẫn tính nếu thấy rõ và audio hỗ trợ. Giữ người nói ổn định trong cảnh toàn nhiều người.
JSON {"scenes":[{"start":0,"end":3,"kind":"speaker","speaker":"mô tả ngoại hình ngắn","visible_speaking":true,"confidence":0.9,"reason":"bằng chứng nghe và nhìn","keyframes":[{"time":0,"face":[0.6,0.1,0.75,0.35]}]}]}.
Thời lượng file: '''+str(length)+' giây. Transcript tham chiếu: '+json.dumps(excerpt,ensure_ascii=False)
            raw=google_ai.generate(prompt,[google_ai.media_part(proxy,'video/mp4')])
            raw_scenes = raw if isinstance(raw, list) else raw.get('scenes', []) if isinstance(raw, dict) else []
            if raw_scenes and isinstance(raw_scenes[0], dict) and 'scenes' in raw_scenes[0]:
                raw_scenes = [scene for item in raw_scenes for scene in item.get('scenes', [])]
            chunk=sanitize(raw_scenes,length)
            # Frame observations refine geometry, never voice identity.
            points=refine(proxy,chunk)
            part.write_text(json.dumps({'scenes':chunk,'keyframes':points},ensure_ascii=False))
            chunk={'scenes':chunk,'keyframes':points}
        for s in chunk['scenes']:
            scenes.append({**s,'start':round(s['start']+start,3),'end':round(s['end']+start,3),'keyframes':[{**p,'time':round(p['time']+start,3)} for p in s['keyframes']]})
    points=[]
    for index,start in enumerate(range(0,math.ceil(duration),30)):
        chunk=json.loads((directory/f'shots-{index}.json').read_text())
        for p in chunk['keyframes']:
            points.append({**p,'time':round(p['time']+start,3),'scene':f"{index}:{p['scene']}"})
    result={'version':VERSION,'start':clip['start'],'end':clip['end'],'keyframes':points,'scenes':scenes,'note':'Cảnh người nghe, cảnh trám và đoạn chưa chắc chắn giữ toàn khung; lời thoại tiếp tục nguyên vẹn.','method':'Gemini audio + lip/shot reasoning; OpenCV geometry; conservative fallback'}
    enrich_reactions(directory,result)
    visual_layout(directory,result,source,clip)
    from .face_tracking import refresh_geometry
    refresh_geometry(directory,result)
    temp=directory/'focus.tmp';temp.write_text(json.dumps(result,ensure_ascii=False));temp.replace(directory/'focus.json')
    return result


def enrich_reactions(directory, result):
    """A listener is visual context, not a reassigned speaker. Keep portrait scale."""
    import cv2
    detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    caps={}
    try:
        for p in result['keyframes']:
            if p.get('mode')!='fit' and p.get('kind')!='reaction':continue
            index=int(p['time']//30);proxy=directory/f'shots-{index}.mp4'
            if not proxy.exists():continue
            cap=caps.setdefault(index,cv2.VideoCapture(str(proxy))) if index not in caps else caps[index]
            cap.set(cv2.CAP_PROP_POS_MSEC,(p['time']-index*30)*1000)
            ok,img=cap.read()
            if not ok:continue
            boxes=detector.detectMultiScale(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),scaleFactor=1.1,minNeighbors=5,minSize=(24,24))
            if len(boxes):
                boxes=sorted(boxes,key=lambda b:abs((b[0]+b[2]/2)/img.shape[1]-p['x'])) if p.get('face') else sorted(boxes,key=lambda b:b[2]*b[3],reverse=True)
                x,y,w,h=[float(v) for v in boxes[0]];ih,iw=img.shape[:2]
                p.update(face=[x/iw,y/ih,(x+w)/iw,(y+h)/ih],x=(x+w/2)/iw,mode='crop',visual_context=True)
    finally:
        for cap in caps.values():cap.release()
    result['layout_version']='stable-v3'
    result['note']='Giữ bố cục ổn định trong từng cảnh; cảnh người nghe giữ lời thoại và chân dung khi thấy rõ. Luôn crop dọc 9:16; cảnh chưa chắc người nói ưu tiên khuôn mặt đang thấy và giữ nguyên lời thoại.'


def prepared_track(track, info, settings):
    if settings.get('crop_mode')=='manual':
        from .static_framing import prepare
        return prepare(track,info,settings)
    import statistics
    raw=[dict(p) for p in track['keyframes']] if track.get('reference_tracking') else camera_points(track)
    for p in raw:
        if not p.get('face'):
            nearby=[q for q in raw if q.get('scene')==p.get('scene') and q.get('face')]
            if nearby:
                q=min(nearby,key=lambda q:abs(q['time']-p['time']));p.update(face=q['face'],x=q['x'])
    points=[{**p,**geometry(info,settings,p)} for p in raw]
    # Lock a shot to one feasible crop center. Only move when the subject actually
    # leaves that window; intersect face-safe bounds so smoothing never clips faces.
    groups=[]
    for p in points:
        if not groups or groups[-1][-1].get('scene')!=p.get('scene'):groups.append([])
        groups[-1].append(p)
    for group in groups:
        portraits=[p for p in group if p['mode']=='crop' and p.get('face')]
        if not portraits:continue
        if any(p['mode']=='fit' and p.get('face') for p in group):
            for p in group:p.update(mode='fit',x=.5,y=.5)
            continue
        # Single-frame detector misses in the same scene must not flash full frame.
        for p in group:
            if p['mode']=='fit' and p.get('kind') in ('speaker','reaction') and not p.get('face'):
                q=min(portraits,key=lambda q:abs(q['time']-p['time']))
                p.update({k:q[k] for k in ('x','y','cw','ch','mode','face')})
        for axis,extent,full in [('x','cw',info['width']),('y','ch',info['height'])]:
            center=statistics.median(p[axis] for p in portraits)
            bounds=[]
            for p in portraits:
                x1,y1,x2,y2=p['face'];fw=x2-x1;fh=y2-y1;half=p[extent]/full/2
                left,right=(max(0,x1-fw*.15),min(1,x2+fw*.15)) if axis=='x' else (max(0,y1-fh*.5),min(1,y2+fh*.3))
                bounds.append((max(half,right-half),min(1-half,left+half)))
            lo=max(b[0] for b in bounds);hi=min(b[1] for b in bounds)
            if lo<=hi:
                fixed=max(lo,min(hi,center))
                for p in group:
                    if p['mode']=='crop':p[axis]=fixed
            else:
                previous=portraits[0][axis]
                for p in group:
                    if p['mode']!='crop':continue
                    target=p[axis]
                    if abs(target-previous)<.018:target=previous
                    else:target=previous+(target-previous)*.35
                    # Original geometry already clamps face safety; clamp the
                    # smoothing result again to this sample's face-safe interval.
                    if p.get('face'):
                        x1,y1,x2,y2=p['face'];fw=x2-x1;fh=y2-y1;half=p[extent]/full/2
                        left,right=(max(0,x1-fw*.15),min(1,x2+fw*.15)) if axis=='x' else (max(0,y1-fh*.5),min(1,y2+fh*.3))
                        target=max(half,right-half,min(1-half,left+half,target))
                    p[axis]=target;previous=target
        for i,p in enumerate(group):p['cut']=i==0
    return {**track,'keyframes':points,'prepared':True,'prepared_zoom':settings.get('crop_zoom',1),'holds':calm_holds(track,settings)}


def visual_layout(directory,result,source=None,clip=None):
    """Camera cuts are observed independently of model/chunk boundaries."""
    import cv2
    import bisect
    cuts=[];previous=None
    proxies=sorted(directory.glob('shots-*.mp4'),key=lambda p:int(p.stem.split('-')[1]))
    for proxy in proxies:
        index=int(proxy.stem.split('-')[1]);cap=cv2.VideoCapture(str(proxy));fps=cap.get(cv2.CAP_PROP_FPS) or 6;frame=0
        try:
            while True:
                ok,img=cap.read()
                if not ok:break
                tiny=cv2.resize(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(64,36));t=index*30+frame/fps
                if previous is not None and float(cv2.absdiff(tiny,previous).mean())>24 and (not cuts or t-cuts[-1]>.3):cuts.append(round(t,3))
                previous=tiny;frame+=1
        finally:cap.release()
    if not proxies:return
    if source and clip:
        cap=cv2.VideoCapture(str(source));refined=[]
        result['source_fps']=cap.get(cv2.CAP_PROP_FPS) or 30
        try:
            for cut in cuts:
                cap.set(cv2.CAP_PROP_POS_MSEC,(clip['start']+max(0,cut-.32))*1000)
                previous=None;best=(0,cut)
                while True:
                    ok,img=cap.read()
                    if not ok:break
                    t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000-clip['start']
                    if t>cut+.24:break
                    tiny=cv2.resize(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(64,36))
                    delta=float(cv2.absdiff(tiny,previous).mean()) if previous is not None else 0
                    if delta>best[0]:best=(delta,t)
                    previous=tiny
                refined.append(round(best[1] if best[0]>24 else cut,5))
        finally:cap.release()
        cuts=sorted(set(refined))
    if source and clip:
        transcript=Path(source).parent/'transcript.json'
        words=clip.get('words') or (json.loads(transcript.read_text()) if transcript.exists() else [])
        turns=[]
        for w in words:
            if not w.get('speaker') or w['end']<=clip['start'] or w['start']>=clip['end']:continue
            a=max(0,w['start']-clip['start']);b=min(clip['end']-clip['start'],w['end']-clip['start'])
            if turns and turns[-1]['speaker']==w['speaker'] and a-turns[-1]['end']<2:
                turns[-1]['end']=max(b,turns[-1]['end'])
            else:turns.append({'start':a,'end':b,'speaker':w['speaker']})
        result['speech_turns']=turns
    result['visual_cuts']=cuts
    result['layout_version']='portrait-v5.1'


def camera_points(track):
    import bisect
    raw=sorted(track['keyframes'],key=lambda p:p['time'])
    if 'visual_cuts' not in track:return [dict(p) for p in raw]
    end=track['end']-track['start'];bounds=[0,*[t for t in track['visual_cuts'] if 0<t<end],end];result=[]
    for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
        group=[dict(p) for p in raw if a<=p['time']<b]
        if not group:continue
        # Incoming geometry comes from inside the observed shot, never an old
        # model anchor a few frames across the camera cut.
        interior=[p for p in group if a+.18<=p['time']<b-.18]
        if interior:group=interior
        anchor=group[0]
        result.append({**anchor,'time':a,'scene':f'camera:{i}','cut':True})
        result.extend({**p,'scene':f'camera:{i}','cut':False} for p in group if p['time']>a)
    return result


def calm_holds(track,settings):
    if track.get('reference_tracking'):
        # Selected-subject tracking must keep actual source frames alive.  A
        # visual hold looks like a frozen camera while audio/captions continue,
        # which is worse than exposing an explicitly marked uncertain angle.
        return []
    if not settings.get('calm_short_shots',True):return []
    scenes=track.get('scenes',[]);cuts=track.get('visual_cuts',[]);holds=[]
    # A held frame reads as an intentional beat up to ~1.6s; beyond that it
    # looks like a frozen/broken player. So cap the hold hard, regardless of
    # the user's calm_max_seconds: inserts longer than the cap are left to play
    # live (a real listener shot looks natural) rather than frozen for seconds.
    limit=min(settings.get('calm_max_seconds',4),MAX_HOLD_SECONDS)
    for i,s in enumerate(scenes):
        if not 0<i<len(scenes)-1 or s['kind'] not in ('reaction','wrong_shot','broken','transition') or not .35<=s['end']-s['start']<=limit:continue
        if scenes[i-1]['kind']!='speaker' or scenes[i+1]['kind']!='speaker':continue
        start=min(cuts,key=lambda t:abs(t-s['start'])) if cuts else s['start']
        end=min(cuts,key=lambda t:abs(t-s['end'])) if cuts else s['end']
        if abs(start-s['start'])>.35 or abs(end-s['end'])>.35 or not .35<=end-start<=limit:continue
        holds.append({'start':start,'end':end,'frame_time':round(max(0,start-1/track.get('source_fps',30)),5),'reason':'Giữ hình qua cảnh chèn ngắn; lời thoại tiếp tục.'})
    # Suppress a short angle insert only inside one continuous measured voice
    # turn. A real change of speaker must remain visible; leave recovery space.
    boundaries=[0,*cuts,track.get('end',0)-track.get('start',0)]
    for a,b in zip(boundaries[1:-1],boundaries[2:]):
        if not .35<=b-a<=min(2.5,limit):continue
        if not any(turn['start']<=a-.3 and turn['end']>=b+.3 for turn in track.get('speech_turns',[])):continue
        if any(a<h['end']+2 and b>h['start']-2 for h in holds):continue
        holds.append({'start':a,'end':b,'frame_time':round(max(0,a-1/track.get('source_fps',30)),5),'reason':'Giữ hình qua góc máy ngắn trong cùng lượt nói.'})
    return sorted(holds,key=lambda h:h['start'])


def visual_preview(source,clip,preview_source=None):
    """Fast visual-only portrait while audio-aware analysis runs separately."""
    import cv2
    directory=cache_dir(source,clip);directory.mkdir(exist_ok=True,parents=True)
    path=directory/'visual-preview-v5.json'
    with _layout_lock:
        if path.exists():return json.loads(path.read_text())
        cap=cv2.VideoCapture(str(preview_source or source))
        detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
        points=[];previous=None;center=.5;scene=0
        duration=clip['end']-clip['start'];step=max(1,duration/180)
        try:
            t=0
            while t<duration:
                cap.set(cv2.CAP_PROP_POS_MSEC,(clip['start']+t)*1000);ok,img=cap.read()
                if not ok:break
                h,w=img.shape[:2];img=cv2.resize(img,(480,max(2,round(h*480/w))))
                gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY);tiny=cv2.resize(gray,(64,36))
                cut=previous is None or float(cv2.absdiff(tiny,previous).mean())>24
                if cut:scene+=1
                previous=tiny
                faces=detector.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(20,20))
                p={'time':round(t,3),'mode':'crop','x':center,'scene':scene,'cut':cut,'kind':'uncertain'}
                if len(faces):
                    x,y,fw,fh=max(faces,key=lambda b:b[2]*b[3] if cut else b[2]*b[3]/(1+4*abs((b[0]+b[2]/2)/img.shape[1]-center)))
                    ih,iw=img.shape[:2];center=float((x+fw/2)/iw)
                    p.update(x=center,face=[float(x/iw),float(y/ih),float((x+fw)/iw),float((y+fh)/ih)])
                elif cut:p['x']=.5
                points.append(p);t+=step
        finally:cap.release()
        result={'start':clip['start'],'end':clip['end'],'keyframes':points,'scenes':[], 'provisional':True,'note':'Crop dọc theo khuôn mặt tạm thời; AI đang đối chiếu người nói với âm thanh.'}
        import uuid
        temp=path.with_name(uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(result));temp.replace(path)
        return result
