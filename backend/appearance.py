"""Local appearance comparison for a user-selected face within one source video.

The model is OpenCV SFace (Apache-2.0, OpenCV Zoo).  We compare embeddings only
inside the active source and retain no global identity catalogue or person name.
"""
from functools import lru_cache
from pathlib import Path
import math

MODEL = Path(__file__).parent / 'models' / 'face_recognition_sface_2021dec.onnx'


@lru_cache(maxsize=1)
def recognizer():
    import cv2
    return cv2.FaceRecognizerSF.create(str(MODEL), '')


def portrait(image, box):
    """Return a square, padded local crop suitable for SFace feature extraction."""
    import cv2
    h, w = image.shape[:2]
    x1,y1,x2,y2=box;fw=x2-x1;fh=y2-y1
    left=max(0,int((x1-fw*.32)*w));right=min(w,int((x2+fw*.32)*w))
    top=max(0,int((y1-fh*.35)*h));bottom=min(h,int((y2+fh*.45)*h))
    crop=image[top:bottom,left:right]
    if crop.size==0: raise ValueError('Khuôn mặt không hợp lệ.')
    return cv2.resize(crop,(112,112),interpolation=cv2.INTER_AREA)


def feature(image, box):
    return recognizer().feature(portrait(image,box))


def cosine(reference, candidate):
    import cv2
    value=float(recognizer().match(reference,candidate,cv2.FaceRecognizerSF_FR_COSINE))
    return value if math.isfinite(value) else -1.0


def best_match(reference, image, boxes, minimum=.34, margin=.035):
    """Return a local face only if it clearly matches the selected appearance.

    The margin rejects ambiguous two-person wide shots.  These conservative
    abstentions become verified portrait holds in the editor.
    """
    import cv2
    scored=[]
    for box in boxes:
        try: scored.append((cosine(reference,feature(image,box)),box))
        except (ValueError,cv2.error): pass
    if not scored:return None
    scored.sort(reverse=True,key=lambda row:row[0]);score,box=scored[0]
    runner_up=scored[1][0] if len(scored)>1 else -1
    return box if score>=minimum and score-runner_up>=margin else None
