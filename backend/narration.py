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


def synthesize(text, voice, approval_id=None, mode='prebuilt', profile=None):
    from .schemas import VoiceProfile
    profile = VoiceProfile.model_validate(profile or {}).model_dump()
    if mode not in ('prebuilt', 'designed'): raise ValueError('Chế độ voice không hợp lệ.')
    if mode == 'designed': voice = 'Charon' if profile['gender'] == 'male' else 'Kore'
    if voice not in VOICES:raise ValueError('Chất giọng Google chưa được hỗ trợ.')
    plan=plan_for(text,approval_id)
    key=hashlib.sha256(json.dumps([plan['tts_text'],voice,config.TTS_MODEL,VERSION,mode,profile if mode=='designed' else None],ensure_ascii=False).encode()).hexdigest()
    directory=config.DATA/'jobs'/('voice-'+key[:32]);directory.mkdir(parents=True,exist_ok=True)
    target=directory/'voice.wav'
    with _lock:
        if not target.exists():
            temp=directory/'voice.tmp.wav'
            if mode == 'designed':
                from .voice_profiles import instruction
                google_ai.tts(plan['tts_text'],voice,temp,instruction(profile))
                if profile['speed'] != 1:
                    from .media import ffmpeg
                    fast = directory/'voice.fast.wav'
                    ffmpeg(['-i',temp,'-af',f"atempo={profile['speed']}",fast])
                    fast.replace(temp)
            else:
                google_ai.tts(plan['tts_text'],voice,temp)
            temp.replace(target)
        (directory/'normalization.json').write_text(json.dumps(plan,ensure_ascii=False))
    return target,plan


def align_display(audio, display_text):
    """Align display tokens against actual audio, including expanded numbers/names.

    No proportional fallback: an invalid alignment is actionable, never sold as
    voice-synchronous karaoke. Timings are cached with the exact audio and text.
    """
    from .media import probe
    tokens = display_text.split()
    key = hashlib.sha256((hashlib.sha256(audio.read_bytes()).hexdigest()+display_text).encode()).hexdigest()[:24]
    target = audio.parent/('alignment-'+key+'.json')
    if target.exists(): return json.loads(target.read_text())
    duration = probe(audio)['duration']
    prompt = 'Nghe audio và forced-align từng token HIỂN THỊ sau với cách phát âm thực tế. Số hoặc từ viết tắt có thể được đọc thành nhiều tiếng: trả toàn bộ khoảng phát âm cho token gốc đó. KHÔNG chia đều thời gian. Không sửa, thêm hoặc bớt token. JSON {"words":[{"index":0,"start":0.1,"end":0.4}]} (giây từ đầu audio). Tokens: '+json.dumps(tokens,ensure_ascii=False)
    prompt += f' Audio dài chính xác {duration:.3f} giây. Mốc phải nằm trong khoảng này, tăng dần và không chồng nhau.'
    import math
    import uuid
    error = None
    for attempt in range(2):
        raw = google_ai.generate(prompt,[google_ai.media_part(audio,'audio/wav')])
        rows = raw.get('words',[]) if isinstance(raw,dict) else []
        try:
            if len(rows)!=len(tokens): raise ValueError('Số token không khớp.')
            words=[]; previous=0
            for i,(token,row) in enumerate(zip(tokens,rows)):
                start,end=float(row.get('start',-1)),float(row.get('end',-1))
                if not math.isfinite(start) or not math.isfinite(end) or start<0: raise ValueError(f'Mốc token {i} không hợp lệ.')
                start=max(previous,start); end=min(duration,end)
                if row.get('index')!=i or not all(math.isfinite(x) for x in (start,end)) or not 0<=start<end<=duration or float(row['start'])<previous-.05 or float(row['end'])>duration+.15:
                    raise ValueError(f'Mốc token {i} không hợp lệ.')
                words.append({'text':token,'start':start,'end':end,'speaker':'intro'})
                previous=end
            temp=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            temp.write_text(json.dumps(words,ensure_ascii=False));temp.replace(target)
            return words
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            error=exc
            prompt += f' Lượt trước bị lỗi: {exc}. Nghe lại audio và sửa mốc; không ước lượng chia đều.'
    raise ValueError('Mốc karaoke intro chưa hợp lệ. Thử lại hoặc tắt phụ đề intro.') from error
