"""TalkCut client for the local SCRFD + ArcFace face-engine service.

The engine only receives still frames across Docker's internal network.  It
returns local boxes and temporary normalized appearance embeddings; no face
descriptor is kept in the TalkCut database or sent to Google.
"""
from __future__ import annotations

import math
import os

import httpx

URL = os.getenv('FACE_ENGINE_URL', 'http://face-engine:3210').rstrip('/')
TIMEOUT = float(os.getenv('FACE_ENGINE_TIMEOUT_SECONDS', '90'))


def _encode(image) -> bytes:
    import cv2
    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise ValueError('Không thể chuẩn bị khung hình để nhận diện khuôn mặt.')
    return encoded.tobytes()


def describe(image: object) -> list[dict]:
    """Describe detected local faces, rejecting malformed engine output."""
    try:
        response = httpx.post(URL + '/v1/describe', content=_encode(image), headers={'content-type': 'image/jpeg'}, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ValueError('Bộ máy nhận diện khuôn mặt đang chuẩn bị hoặc chưa sẵn sàng. Hãy thử lại sau ít phút.') from error
    result = []
    for item in payload.get('faces', []):
        try:
            box = [float(value) for value in item['box']]
            embedding = [float(value) for value in item['embedding']]
            valid = (len(box) == 4 and len(embedding) == 512 and all(math.isfinite(value) for value in box + embedding)
                     and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            result.append({'box': box, 'embedding': embedding, 'score': float(item.get('score', 0))})
    return result


def portrait(faces: list[dict]) -> dict | None:
    return max(faces, key=lambda item: (item['box'][2] - item['box'][0]) * (item['box'][3] - item['box'][1]), default=None)


def cosine(reference: list[float], candidate: list[float]) -> float:
    return sum(a * b for a, b in zip(reference, candidate))


def best_match(reference: list[float], faces: list[dict], minimum: float = .35, margin: float = .065) -> dict | None:
    """Three-way decision: accept, abstain/hold, or reject.

    The old photo-search threshold optimizes recall.  Video cuts must favor
    correctness: ambiguous/profile samples become a verified portrait hold,
    never a listener/table crop.
    """
    scored = sorted(((cosine(reference, item['embedding']), item) for item in faces), key=lambda row: row[0], reverse=True)
    if not scored:
        return None
    score, selected = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else -1
    return selected if score >= minimum and score - runner_up >= margin else None
