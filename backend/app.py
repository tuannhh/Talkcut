import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from . import config, store, pipeline, google_ai, presets
from .media import probe, MediaError
from .schemas import ImportRequest, AnalyzeRequest, ClipEdit, Settings, BatchBrand


@asynccontextmanager
async def lifespan(app):
    pipeline.start_worker()
    yield


app = FastAPI(title='TalkCut Studio', lifespan=lifespan)


@app.middleware('http')
async def local_write_guard(request: Request, call_next):
    # This is a local personal tool: deny cross-origin browser writes.
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        from urllib.parse import urlparse
        if origin and urlparse(origin).hostname not in ('localhost', '127.0.0.1', '::1'):
            return JSONResponse({'detail': 'Chỉ cho phép thao tác từ ứng dụng local.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@app.exception_handler(KeyError)
async def not_found(request, exc):
    return JSONResponse({'detail': 'Không tìm thấy dữ liệu.'}, status_code=404)


@app.exception_handler(ValueError)
async def bad_input(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=400)


@app.exception_handler(google_ai.AIError)
def ai_error(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=502)


@app.exception_handler(MediaError)
async def bad_media(request, exc):
    return JSONResponse({'detail': 'Không đọc được video/âm thanh. Hãy kiểm tra file có phát được và dùng MP4 H.264 nếu cần.'}, status_code=400)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'google_configured': bool(config.API_KEY), 'models': {'content': config.CONTENT_MODEL, 'stt': config.STT_MODEL, 'tts': config.TTS_MODEL}, 'source_root': str(config.SOURCE_ROOT), 'max_upload_gb': config.MAX_BYTES / 1024**3}


@app.get('/api/studio')
def studio():
    result = {kind: store.listing(singular) for kind, singular in [('sources', 'source'), ('clips', 'clip'), ('jobs', 'job'), ('exports', 'export'), ('assets', 'asset')]}
    result['assets'] = [a for a in result['assets'] if a.get('path')]
    # Poll only summaries, never entire transcripts and render snapshots.
    for source in result['sources']:
        source.pop('transcript', None)
    for clip in result['clips']:
        clip.pop('words', None)
    for job in result['jobs']:
        job.pop('payload', None)
        job.pop('result', None)
    return result


async def upload(file, target, limit):
    size = 0
    try:
        with target.open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, 'File vượt giới hạn dung lượng.')
                out.write(chunk)
        if size == 0:
            raise ValueError('File rỗng.')
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return size


@app.get('/api/presets')
def list_presets():
    return store.listing('preset')


@app.post('/api/presets')
def create_preset(body: presets.PresetRequest):
    return presets.save(body)


@app.put('/api/presets/{id}')
def update_preset(id: str, body: presets.PresetRequest):
    return presets.save(body,id)


@app.post('/api/presets/{id}/apply')
def apply_preset(id: str, body: Settings):
    return {'settings':presets.apply(id,body.model_dump())}


@app.delete('/api/presets/{id}')
def delete_preset(id: str):
    store.get(id,'preset')
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE id=? AND kind='preset'",(id,))
    return {'deleted':True}


@app.post('/api/sources/upload')
async def upload_source(file: UploadFile = File(...)):
    name = Path(file.filename or 'video.mp4').name
    ext = Path(name).suffix.lower()
    if ext not in ('.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi', '.mts'):
        raise ValueError('Hỗ trợ MP4, MOV, MKV, WEBM, M4V, AVI, MTS.')
    source = store.create('source', {'title': name, 'kind': 'upload', 'status': 'importing'})
    folder = config.DATA / 'sources' / source['id']
    folder.mkdir()
    path = folder / ('original' + ext)
    try:
        await upload(file, path, config.MAX_BYTES)
        # Probe is short and runs off the async request loop.
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(pipeline.finish_source, source, path)
    except Exception:
        store.update(source['id'], status='failed')
        raise


@app.post('/api/sources/import')
def import_source(body: ImportRequest):
    value = pipeline.youtube_url(body.value) if body.kind == 'youtube' else str(pipeline.source_path(body.value))
    source = store.create('source', {'kind': body.kind, 'input': value, 'title': Path(value).name if body.kind == 'path' else 'Video YouTube', 'status': 'importing'})
    return {'source': source, 'job': pipeline.enqueue('import', source['id'])}


@app.post('/api/sources/{id}/analyze')
def analyze(id: str, body: AnalyzeRequest):
    source = store.get(id, 'source')
    if source['status'] not in ('ready', 'analyzed'):
        raise ValueError('Chờ nhập nguồn hoàn tất trước khi phân tích.')
    if not config.API_KEY:
        raise ValueError('Chưa có Google API key trong .env.')
    return pipeline.enqueue('analyze', id, body.model_dump())


@app.post('/api/sources/{id}/refresh-quality')
def refresh_source_quality(id: str):
    source = store.get(id, 'source')
    if source.get('kind') != 'youtube':
        raise ValueError('Chỉ có nguồn YouTube mới có thể tải lại chất lượng.')
    if source.get('status') not in ('ready', 'analyzed'):
        raise ValueError('Chờ nhập nguồn hoàn tất trước khi tải lại chất lượng.')
    return pipeline.enqueue('refresh-quality', id)


@app.get('/api/clips/{id}')
def get_clip(id: str):
    clip = store.get(id, 'clip')
    path = config.DATA / 'sources' / clip['source_id'] / 'transcript.json'
    if clip.get('words') is None:
        all_words = json.loads(path.read_text()) if path.exists() else []
        clip['words'] = [w for w in all_words if w['end'] > clip['start'] and w['start'] < clip['end']]
    clip['settings'] = Settings.model_validate(clip.get('settings', {})).model_dump()
    return clip


@app.put('/api/clips/{id}')
def edit_clip(id: str, body: ClipEdit):
    clip = store.get(id, 'clip')
    source = store.get(clip['source_id'], 'source')
    if body.end > source['duration']:
        raise ValueError('Mốc kết thúc vượt quá thời lượng nguồn.')
    payload = body.model_dump()
    # Moving trim boundaries reloads original word timings for the expanded interval.
    if body.start != clip['start'] or body.end != clip['end']:
        payload['words'] = None
    elif payload['words'] is not None:
        previous = -1
        for w in payload['words']:
            if w['start'] < previous or w['end'] > source['duration']:
                raise ValueError('Các từ phải theo thứ tự thời gian trong nguồn.')
            previous = w['start']
    for field, kind in [('intro_asset', 'image'), ('intro_image_asset', 'image'), ('outro_asset', 'video'), ('music_asset', 'audio'), ('watermark_asset', 'image')]:
        if payload['settings'][field]:
            from .editor import asset
            asset(payload['settings'][field], kind)
    approval_id = payload['settings'].get('intro_approval_id')
    if approval_id:
        approved = store.get(approval_id, 'tts_approval')
        if approved['source_text'] != payload['settings']['intro_text']:
            payload['settings']['intro_approval_id'] = None
    return store.update(id, **payload, revision=clip['revision'] + 1)


@app.post('/api/clips/{id}/render')
def render_clip(id: str):
    clip = store.get(id, 'clip')
    # Snapshot: editing while rendering cannot mutate the in-flight output.
    return pipeline.enqueue('render', id, {'clip': clip})


@app.post('/api/clips/{id}/research')
def research(id: str):
    store.get(id, 'clip')
    return pipeline.enqueue('research', id)


@app.post('/api/clips/apply-brand')
def apply_brand(body: BatchBrand):
    clips = [store.get(id, 'clip') for id in dict.fromkeys(body.clip_ids)]
    brand = {k: v for k, v in body.settings.model_dump().items() if k.startswith(('watermark_', 'caption_', 'music_')) or k in ('brand_color', 'outro_asset')}
    from .editor import asset
    for field, kind in [('outro_asset', 'video'), ('music_asset', 'audio'), ('watermark_asset', 'image')]:
        if brand.get(field):
            asset(brand[field], kind)
    for clip in clips:
        store.update(clip['id'], settings={**clip['settings'], **brand}, revision=clip['revision'] + 1)
    return {'updated': len(clips)}


@app.post('/api/jobs/{id}/retry')
def retry(id: str):
    job = store.get(id, 'job')
    if job['status'] != 'failed':
        raise ValueError('Chỉ thử lại tác vụ bị lỗi.')
    return pipeline.enqueue(job['kind'], job['target'], job['payload'])


@app.post('/api/assets')
async def upload_asset(file: UploadFile = File(...)):
    name = Path(file.filename or 'asset').name
    ext = Path(name).suffix.lower()
    types = {'.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.webp': 'image', '.mp3': 'audio', '.wav': 'audio', '.m4a': 'audio', '.aac': 'audio', '.ogg': 'audio', '.mp4': 'video', '.mov': 'video', '.webm': 'video'}
    if ext not in types:
        raise ValueError('Chọn ảnh PNG/JPG/WEBP, nhạc MP3/WAV/M4A hoặc video MP4/MOV/WEBM.')
    path = config.DATA / 'assets' / (uuid.uuid4().hex + ext)
    await upload(file, path, min(config.MAX_BYTES, 1024**3))
    try:
        type = types[ext]
        if type == 'image':
            with Image.open(path) as im:
                im.verify()
        else:
            info = probe(path)
            if not info['duration'] or (type == 'audio' and not info['has_audio']) or (type == 'video' and not info.get('width')):
                raise ValueError('Tài nguyên không hợp lệ.')
            if type == 'video' and info['duration'] > 120:
                raise ValueError('Outro tối đa 120 giây.')
    except Exception:
        path.unlink(missing_ok=True)
        raise ValueError('Không đọc được tài nguyên hoặc thời lượng vượt giới hạn (outro tối đa 120 giây).') from None
    return store.create('asset', {'name': name, 'type': type, 'path': str(path.relative_to(config.DATA))})


@app.get('/api/exports/{id}/download')
def download(id: str):
    item = store.get(id, 'export')
    return FileResponse(config.DATA / item['path'], media_type='video/mp4', filename='talkcut-' + id[:8] + '-1080x1920.mp4')


@app.get('/media/{path:path}')
def media(path: str):
    target = (config.DATA / path).resolve()
    if not target.is_relative_to(config.DATA) or target.suffix.lower() not in ('.mp4', '.mov', '.webm', '.mkv', '.jpg', '.jpeg', '.png', '.webp', '.mp3', '.wav', '.m4a', '.aac', '.ogg') or not target.is_file():
        raise HTTPException(404)
    return FileResponse(target)


# Editing helpers are independent of the long render queue.
from .tts_normalizer import NormalizeRequest, VoicePreviewRequest, ApprovalRequest, normalize
from . import narration, focus as focusing


@app.get('/api/voices')
def voices():
    return {'voices': narration.VOICES, 'sample': VoicePreviewRequest().text}


@app.post('/api/tts/normalize')
def normalize_tts(body: NormalizeRequest):
    return normalize(body.text, body.context_tags, body.overrides)


@app.post('/api/tts/approve')
def approve_tts(body: ApprovalRequest):
    return narration.approve(body.text, body.tts_text)


@app.post('/api/tts/preview')
def preview_tts(body: VoicePreviewRequest):
    path, plan = narration.synthesize(body.text, body.voice, body.approval_id, body.mode, body.profile.model_dump())
    return {'path': str(path.relative_to(config.DATA)), 'plan': plan}


@app.get('/api/clips/{id}/focus')
def get_focus(id: str, zoom: float | None = Query(None, ge=1, le=2), subject: str | None = None):
    clip = store.get(id, 'clip')
    # This query is the unsaved auto-tracking draft. Do not prepare it with
    # the persisted manual coordinates from the previous editing mode.
    if subject is not None:clip={**clip,'settings':{**clip.get('settings',{}),'tracking_subject':subject or None,'crop_mode':'auto'}}
    if subject:
        from .subject_tracking import reference
        reference(config.DATA/store.get(clip['source_id'],'source')['path'],subject)
    if zoom is not None:clip={**clip,'settings':{**clip.get('settings',{}),'crop_zoom':zoom}}
    source = store.get(clip['source_id'], 'source')
    plan = focusing.cached(config.DATA / source['path'], clip)
    if plan:
        settings=Settings.model_validate(clip.get('settings',{})).model_dump()
        plan=focusing.prepared_track(plan,source,settings)
        plan['holds']=focusing.calm_holds(plan,settings)
        directory=focusing.cache_dir(config.DATA/source['path'],clip)
        for h in plan['holds']:
            if h.get('path'):continue
            path=directory/f'hold-v6-{h["frame_time"]:.3f}-{settings["crop_zoom"]}.jpg'
            if not path.exists():
                temp=path.with_name(uuid.uuid4().hex+'.jpg')
                freeze(config.DATA/source['path'],{**clip,'settings':settings},clip['start']+h['frame_time'],temp);temp.replace(path)
            h['path']=str(path.relative_to(config.DATA))
    preview_plan=None
    # Never run hundreds of video seeks synchronously just to open a clip.
    # A plan is prepared explicitly; an unprepared crop is not a verified preview.
    return {'plan':plan,'preview_plan':preview_plan,'labels':focusing.LABELS}


@app.post('/api/clips/{id}/static-framing')
def static_framing(id: str, body: ClipEdit):
    from .static_framing import cached_track
    from .intro_art import freeze
    import hashlib
    saved=store.get(id,'clip');clip={**saved,**body.model_dump()}
    source=store.get(clip['source_id'],'source');settings=clip['settings']
    if clip['end']>source['duration']:raise ValueError('Mốc kết thúc vượt quá thời lượng nguồn.')
    settings['crop_mode']='manual'
    track=cached_track(config.DATA/source['path'],clip)
    plan=focusing.prepared_track(track,source,settings)
    token=hashlib.sha256(json.dumps([id,clip['start'],clip['end'],settings],sort_keys=True).encode()).hexdigest()[:24]
    directory=config.DATA/'jobs'/('static-'+token);directory.mkdir(parents=True,exist_ok=True)
    for h in plan['holds']:
        path=directory/f'hold-{h["frame_time"]:.5f}.jpg'
        if not path.exists():
            temp=directory/(uuid.uuid4().hex+'.jpg')
            freeze(config.DATA/source['path'],clip,clip['start']+h['frame_time'],temp);temp.replace(path)
        h['path']=str(path.relative_to(config.DATA))
    return {'plan':plan}


@app.get('/api/clips/{id}/subjects')
def subject_gallery(id: str, time: float | None = Query(None,ge=0)):
    from .subject_tracking import candidates
    clip=store.get(id,'clip');source=store.get(clip['source_id'],'source')
    return {'items':candidates(config.DATA/source['path'],clip,time)}


@app.post('/api/clips/{id}/focus')
def prepare_focus(id: str):
    clip = store.get(id, 'clip')
    source = store.get(clip['source_id'], 'source')
    plan = focusing.cached(config.DATA / source['path'], clip)
    if plan:
        return {'ready': True}
    return pipeline.enqueue('focus', id, {'clip': clip})


@app.post('/api/clips/{id}/intro-suggestion')
def suggest_intro(id: str, body: ClipEdit):
    store.get(id, 'clip')
    text = ' '.join(w.text for w in (body.words or []) if body.start <= w.start < body.end)
    result = google_ai.generate('Viết lời mở đầu tiếng Việt 1–2 câu, khoảng 25–45 từ, dẫn vào đoạn talk sau. Khác tiêu đề, gợi vấn đề và lý do đáng nghe. Chỉ dựa vào nội dung được cung cấp; không bịa số liệu, lời hứa, danh tính hay kết luận pháp lý. Trả JSON {"intro_text":"..."}. DỮ LIỆU: ' + json.dumps({'title': body.title, 'summary': body.summary, 'transcript': text}, ensure_ascii=False))
    suggestion = str(result.get('intro_text', '')).strip()
    if not suggestion or len(suggestion) > 700:
        raise ValueError('Lời mở đầu AI chưa hợp lệ. Hãy thử lại.')
    return {'intro_text': suggestion}


@app.post('/api/clips/{id}/intro-preview')
def intro_preview(id: str, body: ClipEdit):
    store.get(id, 'clip')
    from .editor import intro_card
    import hashlib
    settings = body.settings.model_dump()
    key = hashlib.sha256(json.dumps(['photo-v6', id, body.start, body.end, settings, body.title], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]
    directory = config.DATA / 'jobs' / ('intro-' + key)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'intro.png'
    meta = directory / 'layout.json'
    if not meta.exists() or not path.exists():
        temporary = directory / (uuid.uuid4().hex + '.png')
        layers = intro_card(settings, temporary, lambda *args: None, body.title, {**store.get(id,'clip'),**body.model_dump()})
        temporary.replace(path)
        for suffix in ('base','title'):
            layer_path=temporary.with_name(temporary.stem+'-'+suffix+'.png')
            if layer_path.exists():layer_path.replace(directory/('intro-'+suffix+'.png'))
        meta_temp = directory / (uuid.uuid4().hex + '.json')
        meta_temp.write_text(json.dumps(layers))
        meta_temp.replace(meta)
    return {'path': str(path.relative_to(config.DATA)), 'base_path': str((directory/'intro-base.png').relative_to(config.DATA)) if (directory/'intro-base.png').exists() else None, 'title_path': str((directory/'intro-title.png').relative_to(config.DATA)) if (directory/'intro-title.png').exists() else None, 'layers': json.loads(meta.read_text())}


@app.post('/api/clips/{id}/intro-layout')
def suggest_intro_layout(id: str, body: ClipEdit):
    store.get(id, 'clip')
    from .editor import asset
    settings = body.settings.model_dump()
    bg = asset(settings['intro_asset'], 'image')
    if not bg:
        return {k:v for k,v in Settings().model_dump().items() if k in ('intro_x','intro_y','intro_color','intro_title_x','intro_title_y','intro_title_color')}
    # Analyze the same portrait crop used in the final card.
    from PIL import ImageOps
    import io, base64
    buffer = io.BytesIO()
    with Image.open(bg) as image:
        ImageOps.fit(image.convert('RGB'), (540,960)).save(buffer, format='JPEG')
    result = google_ai.generate('Phân tích nền intro 9:16. Trả bounding box của TẤT CẢ logo, chữ có sẵn và khuôn mặt cần tránh: [x1,y1,x2,y2] tỷ lệ 0..1. Không coi vùng nền trống là logo. Đồng thời gợi ý màu chữ HEX tương phản cho lời mở đầu ở trên và tiêu đề ở dưới. JSON {"exclusions":[[0.1,0.55,0.95,0.66]],"intro_color":"#1a253c","intro_title_color":"#ffffff"}.', [{'inlineData':{'mimeType':'image/jpeg','data':base64.b64encode(buffer.getvalue()).decode()}}])
    if not isinstance(result, dict):
        raise ValueError('AI chưa trả vùng logo hợp lệ. Hãy thử lại hoặc đặt chữ thủ công.')
    from .editor import fit_intro_regions
    regions = fit_intro_regions(settings, body.title, result.get('exclusions', []))
    changes = {**regions, **{k:result[k] for k in ('intro_color','intro_title_color') if k in result}}
    valid = Settings.model_validate({**settings, **changes}).model_dump()
    return {k:valid[k] for k in changes}


@app.post('/api/clips/{id}/intro-frames')
def intro_frames(id: str, body: ClipEdit, refresh: bool = False):
    from .intro_art import suggestions
    clip={**store.get(id,'clip'),**body.model_dump()}
    return {'frames':suggestions(clip,refresh)}


@app.post('/api/clips/{id}/intro-title')
def intro_title(id: str, body: ClipEdit):
    store.get(id,'clip')
    result=google_ai.generate('Viết tiêu đề intro tiếng Việt ngắn tối đa 12 từ, đúng nội dung, không giật tít hoặc bịa số liệu. JSON {"title":"..."}. Tiêu đề clip: '+body.title+'\nTóm tắt: '+body.summary)
    if not isinstance(result,dict) or not isinstance(result.get('title'),str):raise ValueError('AI chưa trả tiêu đề hợp lệ.')
    return {'title':result['title'][:180]}


@app.post('/api/clips/{id}/intro-audio')
def intro_audio(id: str, body: ClipEdit):
    store.get(id,'clip');s=body.settings.model_dump()
    path,plan=narration.synthesize(s['intro_text'],s['intro_voice'],s.get('intro_approval_id'),s['intro_voice_mode'],s['intro_voice_profile'])
    words=narration.align_display(path,s['intro_text']) if s['intro_caption_enabled'] else []
    from .media import probe
    return {'path':str(path.relative_to(config.DATA)),'words':words,'duration':probe(path)['duration']}


static = config.ROOT / 'frontend' / 'dist'
if static.exists():
    app.mount('/', StaticFiles(directory=static, html=True), name='frontend')
