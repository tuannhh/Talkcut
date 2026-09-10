"""User-selected visual reference, relocated independently in each camera shot.

This matches an appearance within a video, not a speaker's real-world identity.
Missing observations abstain from a new face decision but retain moving source
video; a talking clip must never silently turn into a frozen portrait.
"""
import hashlib
import json
import math
import re
import threading
from pathlib import Path
from . import config
from .media import ffmpeg
from .face_engine import describe, portrait, best_match

_lock = threading.RLock()
VERSION = 'reference-v5-dynamic-arcface'


def reference(source, token):
    if not token or not re.fullmatch(r'[a-f0-9]{24}', token):
        raise ValueError('Ảnh tham chiếu chủ thể không hợp lệ.')
    path = Path(source).parent / 'subjects' / (token + '.json')
    if not path.exists():
        raise ValueError('Không tìm thấy ảnh chủ thể trong nguồn này. Chọn lại khuôn mặt.')
    return json.loads(path.read_text())


def candidates(source, clip, seconds=None):
    """Small on-demand gallery; show samples rather than pretending to deduplicate identities."""
    import cv2
    directory = Path(source).parent / 'subjects'; directory.mkdir(exist_ok=True)
    times = [seconds] if seconds is not None else [clip['start']+(clip['end']-clip['start'])*f for f in (.01,.08,.2,.4,.65,.85)]
    if any(not clip['start'] <= t < clip['end'] for t in times):
        raise ValueError('Chọn khung hình trong clip.')
    key = hashlib.sha256(json.dumps([VERSION, times]).encode()).hexdigest()[:24]
    cache = directory / ('gallery-'+key+'.json')
    with _lock:
        if cache.exists(): return json.loads(cache.read_text())
        cap = cv2.VideoCapture(str(source));items=[]
        try:
            for t in times:
                cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,img=cap.read()
                if not ok:continue
                h,w=img.shape[:2]
                for candidate in sorted(describe(img),key=lambda item:(item['box'][2]-item['box'][0])*(item['box'][3]-item['box'][1]),reverse=True)[:4]:
                    box=candidate['box']
                    x1,y1,x2,y2=box;fw=x2-x1;fh=y2-y1
                    if fw<.035 or fh<.07:continue
                    token=hashlib.sha256(json.dumps([str(source),round(t,3),box]).encode()).hexdigest()[:24]
                    # Include shoulders/hair to support matching during profile turns.
                    left=max(0,int((x1-fw*.5)*w));right=min(w,int((x2+fw*.5)*w))
                    top=max(0,int((y1-fh*.4)*h));bottom=min(h,int((y2+fh*1.2)*h))
                    target=directory/(token+'.jpg')
                    portrait=img[top:bottom,left:right];portrait=cv2.resize(portrait,(240,max(1,round(portrait.shape[0]*240/portrait.shape[1]))))
                    cv2.imwrite(str(target),portrait)
                    record={'id':token,'time':round(t,3),'face':box,'path':str(target.relative_to(config.DATA))}
                    (directory/(token+'.json')).write_text(json.dumps(record))
                    items.append(record)
        finally:cap.release()
        cache.write_text(json.dumps(items));return items


def observations(raw, samples):
    """Model cannot invent timestamps or accept low-confidence/faulty rectangles."""
    rows=raw.get('observations',[]) if isinstance(raw,dict) else []
    by_id={}
    for r in rows:
        if not isinstance(r,dict) or not isinstance(r.get('id'),int):continue
        i=r['id'];box=r.get('face')
        try:
            valid=(r.get('visible') is True and float(r.get('confidence',0))>=.8 and len(box)==4
                   and all(math.isfinite(float(v)) for v in box)
                   and 0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1
                   and .025<=box[2]-box[0]<=.65 and .045<=box[3]-box[1]<=.9)
        except (TypeError,ValueError):valid=False
        if valid:by_id[i]=box
    return [{**s,'face':by_id.get(s['id'])} for s in samples]


def appearance_observations(raw, samples):
    """Accept only a model-selected *local* face, never its freehand box.

    Gemini is useful for deciding whether two portraits look alike, but its
    normalized coordinates can drift when a wide two-person shot is resized.
    Each offered candidate below comes from the local detector, so an absent
    profile becomes an abstention/hold instead of a crop toward the listener.
    """
    chosen = {}
    for row in raw.get('matches', []) if isinstance(raw, dict) else []:
        try:
            ident = int(row['id']); candidate = int(row['candidate'])
            confidence = float(row.get('confidence', 0))
        except (KeyError, TypeError, ValueError):
            continue
        if row.get('visible') is True and confidence >= .82:
            chosen[ident] = candidate
    result=[]
    for sample in samples:
        candidate=chosen.get(sample['id'])
        boxes=sample.get('faces', [])
        face=boxes[candidate] if candidate is not None and 0 <= candidate < len(boxes) else None
        result.append({**sample, 'face':face})
    return result


def assemble(samples, cuts, clip, token):
    """One portrait per shot unless its face-safe intersection requires real motion."""
    duration=clip['end']-clip['start'];bounds=[0,*cuts,duration];points=[];scenes=[];missing=[];accepted=[]
    for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
        group=[s for s in samples if s['shot']==i and s.get('face')]
        # Split detections into a consistent spatial track; one distant false match
        # must not drag a seated subject across the shot.
        if len(group)>=3:
            import statistics
            centers=[(p['face'][0]+p['face'][2])/2 for p in group]
            median=statistics.median(centers)
            close=[p for p in group if abs((p['face'][0]+p['face'][2])/2-median)<.16]
            if len(close)>=math.ceil(len(group)*.7):group=close
        kind='selected' if group else 'uncertain'
        reason='Theo chủ thể đã chọn; xác định lại vị trí trong góc máy này.' if group else 'Chưa nhận diện đủ chắc chủ thể ở góc máy này: giữ video đang chuyển động, cần duyệt lại.'
        scene={'start':a,'end':b,'kind':kind,'speaker':'Chủ thể đã chọn','reason':reason,'confidence':.9 if group else 0,'keyframes':[]}
        if group:
            accepted.extend(group)
            for j,p in enumerate(group):
                box=p['face'];point={'time':a if j==0 else p['time'],'face':box,'x':(box[0]+box[2])/2,'mode':'crop','kind':kind,'scene':f'camera:{i}','cut':j==0}
                points.append(point);scene['keyframes'].append(point)
        else:missing.append((a,b))
        scenes.append(scene)
    if not points:raise ValueError('Chưa tìm thấy chắc chủ thể trong clip. Chọn ảnh rõ mặt hơn và thử lại; không dựng crop vào giữa cảnh.')
    fallbacks=[]
    for a,b in missing:
        prior=[p for p in accepted if p['time']<a]
        verified=prior[-1] if prior else accepted[0]
        # Keep the source moving during an ambiguous camera shot.  The last
        # confirmed geometry is only an anchor for the crop, never a replacement
        # JPEG; reviewers can still see the actual camera footage and subtitles.
        fallbacks.append({'start':a,'end':b,'anchor_time':verified['time'],'reason':'Không đủ chắc chắn để đổi chủ thể; giữ chuyển động gốc với khung neo gần nhất.'})
        box=verified['face'];points.append({'time':a,'face':box,'x':(box[0]+box[2])/2,'mode':'crop','kind':'uncertain','scene':f'hold:{a}','cut':True})
    return {'version':VERSION,'start':clip['start'],'end':clip['end'],'subject':token,'reference_tracking':True,
            'keyframes':sorted(points,key=lambda p:p['time']),'scenes':scenes,'visual_cuts':cuts,'reference_holds':[], 'dynamic_fallbacks':fallbacks,
            'note':f'Theo chủ thể đã chọn qua từng góc máy. {len(missing)} cảnh cần duyệt (video vẫn chuyển động, lời thoại tiếp tục).',
            'layout_version':'portrait-v5.1','geometry_version':'face-v9-arcface'}


def analyze(source, clip, progress):
    import cv2
    from . import focus
    token=clip['settings']['tracking_subject'];ref=reference(source,token)
    reference_image=cv2.imread(str(config.DATA/ref['path']))
    reference_face=portrait(describe(reference_image))
    if not reference_face:
        raise ValueError('Ảnh tham chiếu chưa thấy khuôn mặt rõ. Chọn một ảnh khác trong thư viện khuôn mặt.')
    reference_embedding=reference_face['embedding']
    directory=focus.cache_dir(source,clip);directory.mkdir(exist_ok=True,parents=True)
    # Native cuts are preserved; model observation boundaries never create cuts.
    duration=clip['end']-clip['start'];base=focus.cache_dir(source,{**clip,'settings':{}})
    for i,a in enumerate(range(0,math.ceil(duration),30)):
        proxy=directory/f'shots-{i}.mp4';old=base/proxy.name
        if not proxy.exists():
            if old.exists():
                import shutil
                shutil.copyfile(old,proxy)
            else:ffmpeg(['-ss',str(clip['start']+a),'-i',source,'-t',str(min(30,duration-a)),'-vf','scale=720:-2,fps=6','-an','-c:v','libx264','-preset','ultrafast','-crf','24',proxy])
    progress('Đang tách góc máy để tìm lại chủ thể',15)
    layout={};focus.visual_layout(directory,layout,source,clip)
    cuts=layout.get('visual_cuts',[]);bounds=[0,*cuts,duration];samples=[];caps={}
    try:
        for shot,(a,b) in enumerate(zip(bounds,bounds[1:])):
            # The portrait is intentionally locked per camera shot. Two
            # samples are sufficient in a long shot; scanning every 1.5s
            # slowed the focus job without improving the stable result.
            count=1 if b-a <= 10 else 2
            for j in range(count):
                t=a+(b-a)*(j+.5)/count;i=int(t//30)
                if i not in caps:caps[i]=cv2.VideoCapture(str(directory/f'shots-{i}.mp4'))
                cap=caps[i];cap.set(cv2.CAP_PROP_POS_MSEC,(t-i*30)*1000);ok,img=cap.read()
                if not ok:continue
                ident=len(samples);path=directory/f'observation-{ident}.jpg';cv2.imwrite(str(path),img)
                samples.append({'id':ident,'shot':shot,'time':round(t,5),'path':str(path)})
    finally:
        for c in caps.values():c.release()
    # The engine owns two ONNX workers. This background pass keeps the web
    # preview responsive while avoiding sequential waits for each still.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def match_sample(sample):
        image=cv2.imread(sample['path'])
        match=best_match(reference_embedding,describe(image)) if image is not None else None
        return {**sample,'face':match['box'] if match else None}
    prepared=[]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(match_sample,sample) for sample in samples]
        for index,future in enumerate(as_completed(futures),1):
            prepared.append(future.result())
            if index == len(samples) or index % 4 == 0:
                progress(f'Đang đối chiếu chân dung đã chọn · {index}/{len(samples)}',20+int(index/max(1,len(samples))*65))
    samples=sorted(prepared,key=lambda sample:sample['id'])
    result=assemble(samples,cuts,clip,token);result['source_fps']=layout.get('source_fps',30)
    result['speech_turns']=layout.get('speech_turns',[])
    temp=directory/'focus.tmp';temp.write_text(json.dumps(result,ensure_ascii=False));temp.replace(directory/'focus.json')
    return result


def hold_images(source,clip,plan):
    """Compatibility hook for cached callers; selected-subject plans never freeze."""
    return plan
