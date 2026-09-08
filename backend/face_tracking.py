"""Face geometry refinement anchored to audio-aware speaker observations."""
import math
from functools import lru_cache

@lru_cache(maxsize=1)
def detectors():
    import cv2
    return [cv2.CascadeClassifier(cv2.data.haarcascades+name) for name in
            ('haarcascade_frontalface_default.xml','haarcascade_profileface.xml')]


def faces(image, anchor=None):
    import cv2
    if image.shape[1]>480:image=cv2.resize(image,(480,round(image.shape[0]*480/image.shape[1])))
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);h,w=gray.shape
    frontal,profile=detectors();boxes=[]
    for detector,flip in ((frontal,False),(profile,False),(profile,True)):
        view=cv2.flip(gray,1) if flip else gray
        for x,y,bw,bh in detector.detectMultiScale(view,scaleFactor=1.1,minNeighbors=5,minSize=(18,18)):
            x=w-x-bw if flip else x
            box=[float(x/w),float(y/h),float((x+bw)/w),float((y+bh)/h)]
            if not any(sum(abs(a-b) for a,b in zip(box,old))<.06 for old in boxes):boxes.append(box)
        if anchor is not None and choose_face(boxes,anchor)!=list(anchor):break
    return boxes


def choose_face(boxes, anchor):
    """Reject mouth-sized false positives and other people; retain anchor on misses."""
    x1,y1,x2,y2=anchor;cx=(x1+x2)/2;aw=x2-x1
    candidates=[]
    for box in boxes:
        a,b,c,d=box;ratio=(c-a)/aw;dx=abs((a+c)/2-cx)
        if .55<=ratio<=1.95 and dx<min(.14,aw*.8+.025) and abs((b+d-y1-y2)/2)<.25:
            candidates.append((dx+abs(math.log(ratio))*.035,box))
    return min(candidates,key=lambda item:item[0])[1] if candidates else list(anchor)


def refresh_geometry(directory, result):
    """Refresh cached observations without changing accepted cuts, holds or audio."""
    import cv2
    caps={}
    try:
        for p in result['keyframes']:
            if p.get('kind')!='speaker':continue
            scene=next((s for s in result.get('scenes',[]) if s['start']<=p['time']<s['end'] and s.get('keyframes') and s['kind']=='speaker'),None)
            if not scene:continue
            anchor=min(scene['keyframes'],key=lambda q:abs(q['time']-p['time']))['face']
            index=int(p['time']//30);proxy=directory/f'shots-{index}.mp4'
            if not proxy.exists():continue
            if index not in caps:caps[index]=cv2.VideoCapture(str(proxy))
            cap=caps[index];cap.set(cv2.CAP_PROP_POS_MSEC,(p['time']-index*30)*1000);ok,img=cap.read()
            if not ok:continue
            box=choose_face(faces(img,anchor),anchor)
            p.update(face=box,x=(box[0]+box[2])/2,mode='crop')
    finally:
        for cap in caps.values():cap.release()
    result['geometry_version']='face-v6'
