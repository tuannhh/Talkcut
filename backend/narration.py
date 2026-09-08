import hashlib
import json
import threading
from . import config, google_ai, store
from .tts_normalizer import normalize, VERSION

VOICES=['Kore','Puck','Charon','Aoede','Fenrir','Leda','Orus','Zephyr']
_lock=threading.Lock()


def approve(text, tts_text):
    plan=normalize(text)
    return store.create('tts_approval',{**plan,'tts_text':tts_text.strip(),'requires_review':False,'approved':True})


def plan_for(text, approval_id=None):
    plan=normalize(text)
    if approval_id:
        approved=store.get(approval_id,'tts_approval')
        if approved['source_hash']!=plan['source_hash'] or approved['normalizer_version']!=VERSION or approved['pronunciation_dictionary_version']!=plan['pronunciation_dictionary_version']:
            raise ValueError('Lời mở đầu hoặc quy ước đọc đã thay đổi. Hãy kiểm tra và duyệt lại bản đọc TTS.')
        plan=approved
    if plan['requires_review']:
        raise ValueError('Cách đọc cần kiểm tra: '+', '.join(plan['warnings'])+'. Mở “Kiểm tra cách đọc”, sửa nếu cần và duyệt bản đọc trước khi nghe hoặc dựng.')
    return plan


def synthesize(text, voice, approval_id=None):
    if voice not in VOICES:raise ValueError('Chất giọng Google chưa được hỗ trợ.')
    plan=plan_for(text,approval_id)
    key=hashlib.sha256(json.dumps([plan['tts_text'],voice,config.TTS_MODEL,VERSION],ensure_ascii=False).encode()).hexdigest()
    directory=config.DATA/'jobs'/('voice-'+key[:32]);directory.mkdir(parents=True,exist_ok=True)
    target=directory/'voice.wav'
    with _lock:
        if not target.exists():
            temp=directory/'voice.tmp.wav'
            google_ai.tts(plan['tts_text'],voice,temp)
            temp.replace(target)
        (directory/'normalization.json').write_text(json.dumps(plan,ensure_ascii=False))
    return target,plan
