"""Audio-aware shot planning. Unknown/off-screen shots keep the full image and audio.

The same versioned plan is used in the browser and FFmpeg; face detection refines
geometry only and never decides who is speaking.
"""
import hashlib
import json
import math
from pathlib import Path
from . import config, google_ai
from .media import ffmpeg

VERSION = 'speaker-shots-v2.2'
KINDS = {'speaker', 'reaction', 'broll', 'wrong_shot', 'broken', 'transition', 'end', 'uncertain'}
LABELS = {'speaker': 'Người đang nói', 'reaction': 'Cảnh người nghe', 'broll': 'Cảnh trám', 'wrong_shot': 'Có thể quay nhầm', 'broken': 'Hình lỗi / mất nét', 'transition': 'Chuyển cảnh / lia máy', 'end': 'Kết cảnh', 'uncertain': 'Chưa đủ bằng chứng'}


def cache_dir(source, clip):
    stat = Path(source).stat()
    identity = [VERSION, str(source), stat.st_size, stat.st_mtime_ns, clip['start'], clip['end'], config.CONTENT_MODEL]
    key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
    return config.DATA / 'jobs' / ('focus-' + key)


def cached(source, clip):
    path = cache_dir(source, clip) / 'focus.json'
    return json.loads(path.read_text()) if path.exists() else None


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
    """Safe portrait window: face + headroom stay inside, otherwise fit."""
    iw, ih = info['width'], info['height']
    zoom = settings.get('crop_zoom', 1)
    cw = max(2, int(min(iw, ih*9/16)/zoom)//2*2)
    ch = max(2, int(min(ih, iw*16/9)/zoom)//2*2)
    if p.get('mode') == 'fit':
        return {'mode':'fit', 'x':.5, 'y':.5, 'cw':cw, 'ch':ch}
    face = p.get('face')
    cx = p.get('x', .5)
    cy = .5
    if face:
        x1,y1,x2,y2 = face
        fw,fh = x2-x1,y2-y1
        # Include hair, chin and a margin; never choose the center of a table.
        left,right = max(0,x1-fw*.15),min(1,x2+fw*.15)
        top,bottom = max(0,y1-fh*.5),min(1,y2+fh*.3)
        if (right-left)*iw > cw or (bottom-top)*ih > ch:
            return {'mode':'fit','x':.5,'y':.5,'cw':cw,'ch':ch}
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
            ffmpeg(['-ss',str(clip['start']+start),'-i',source,'-t',str(length),'-vf','scale=720:-2,fps=6','-c:v','libx264','-preset','ultrafast','-crf','24','-c:a','aac','-b:a','64k',proxy])
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
    temp=directory/'focus.tmp';temp.write_text(json.dumps(result,ensure_ascii=False));temp.replace(directory/'focus.json')
    return result


def prepared_track(track, info, settings):
    return {**track,'keyframes':[{**p,**geometry(info,settings,p)} for p in track['keyframes']]}
