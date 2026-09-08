import json
import os
import tempfile
from pathlib import Path
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='talkcut-tests-')
import pytest
from fastapi.testclient import TestClient
from backend import config, store
from backend.app import app
from backend.schemas import Settings, AnalyzeRequest, ClipEdit
from backend.pipeline import youtube_url, source_path, validate_candidates, transcript_segments
from backend.google_ai import parse_words, offset
from backend.editor import make_ass, crop_filter, validate_track, watermark_image


def test_google_word_annotations_preserve_real_timestamps():
    data={'steps':[{'content':[{'annotations':[{'type':'word_info','text':'Thuế','speaker':'spk_1','start_offset':'1.120s','end_offset':'1.540s'},{'type':'citation','text':'not speech'},{'type':'word_info','text':'','start_offset':'2s','end_offset':'1s'}]}]}]}
    assert parse_words(data)==[{'text':'Thuế','speaker':'spk_1','start':1.12,'end':1.54}]
    assert offset({'seconds':2,'nanos':500000000})==2.5


@pytest.mark.parametrize('url',['https://youtube.com/watch?v=abcdefghijk','https://youtu.be/abcdefghijk?t=12','https://www.youtube.com/shorts/abcdefghijk'])
def test_youtube_canonicalizes_video_only(url):
    assert youtube_url(url)=='https://www.youtube.com/watch?v=abcdefghijk'


@pytest.mark.parametrize('url',['http://youtube.com/watch?v=abcdefghijk','https://youtube.com.evil.test/watch?v=abcdefghijk','https://localhost/watch?v=abcdefghijk','https://youtube.com/playlist?list=abcdefghijk','https://user:pass@youtube.com/watch?v=abcdefghijk'])
def test_rejects_arbitrary_network_targets(url):
    with pytest.raises(ValueError):youtube_url(url)


def test_path_import_confined_and_symlinks_resolved(tmp_path,monkeypatch):
    allowed=tmp_path/'allowed';allowed.mkdir()
    outside=tmp_path/'outside.mp4';outside.write_bytes(b'x')
    (allowed/'link.mp4').symlink_to(outside)
    monkeypatch.setattr(config,'SOURCE_ROOT',allowed)
    with pytest.raises(ValueError):source_path(str(outside))
    with pytest.raises(ValueError):source_path(str(allowed/'link.mp4'))
    video=allowed/'in.mp4';video.write_bytes(b'video')
    assert source_path(str(video))==video


def test_invalid_clip_range_and_nan():
    with pytest.raises(ValueError):AnalyzeRequest(min_seconds=90,max_seconds=30)
    with pytest.raises(ValueError):ClipEdit(title='a',summary='b',start=30,end=20)
    with pytest.raises(ValueError):ClipEdit(title='a',summary='b',start=float('nan'),end=50)
    with pytest.raises(ValueError):Settings(caption_color="red;movie=/etc/passwd")


def test_candidate_dedup_and_out_of_range():
    words=[{'start':i,'end':i+.8,'text':'word'} for i in range(80)]
    raw=[{'start':10,'end':30,'title':'A','score':92},{'start':11,'end':31,'title':'duplicate'},{'start':90,'end':100,'title':'outside'},{'start':float('nan'),'end':40,'title':'nan'}]
    found=validate_candidates(raw,words,80,12,35)
    assert len(found)==1
    assert found[0]['start']==9.88 and found[0]['end']==29.98


def test_subtitle_exact_events_and_escaping(tmp_path):
    words=[{'text':'Xin {\\pos(0,0)}','start':10.1,'end':10.4,'speaker':'1'},{'text':'chào','start':10.6,'end':11,'speaker':'1'}]
    path=tmp_path/'caption.ass'
    make_ass(words,{'start':10,'end':12},Settings().model_dump(),path)
    data=path.read_text()
    assert '0:00:00.10,0:00:00.40' in data
    assert '0:00:00.40,0:00:00.60' in data # neutral silence, no fabricated active word
    assert '{\\pos(0,0)}' not in data
    assert 'chào' in data and 'FFFFFF' in data


def test_portrait_crop_never_exceeds_source():
    for w,h in [(1920,1080),(1080,1920),(576,1024),(1024,768)]:
        vf=crop_filter({'width':w,'height':h},Settings(crop_mode='center').model_dump())
        values=vf.split(':')
        assert int(values[0].split('=')[1])<=w
        assert int(values[1])<=h
    assert 'pad=1080:1920' in crop_filter({'width':1920,'height':1080},Settings(crop_mode='fit').model_dump())


def test_focus_track_sanitization():
    track=validate_track([{'time':0,'x':.2},{'time':2,'x':.8},{'time':2,'x':.7},{'time':500,'x':.5},{'time':4,'x':float('nan')}],10)
    assert track==[{'time':0.0,'x':.2},{'time':2.0,'x':.7}]


def test_watermark_clamped_visible(tmp_path):
    from PIL import Image
    for x,y in [(0,0),(1,1)]:
        p=tmp_path/f'{x}.png'
        watermark_image(Settings(watermark_x=x,watermark_y=y,watermark_text='KÊNH DOANH NGHIỆP').model_dump(),p)
        im=Image.open(p)
        assert im.size==(1080,1920)
        assert im.getbbox() is not None
        assert max(im.getchannel('A').getextrema())<=141


def test_api_blocks_cross_origin_writes_and_private_files():
    client=TestClient(app)
    r=client.post('/api/sources/import',headers={'Origin':'https://evil.test'},json={'kind':'path','value':'/etc/passwd'})
    assert r.status_code==403
    assert client.get('/media/studio.sqlite').status_code==404
    assert client.get('/media/../.env').status_code!=200
    assert client.get('/api/health').status_code==200
    assert 'GEMINI_API_KEY' not in client.get('/api/health').text


def test_clip_edit_boundary_and_snapshot(monkeypatch):
    client=TestClient(app)
    s=store.create('source',{'duration':100,'status':'ready'})
    c=store.create('clip',{'source_id':s['id'],'start':10,'end':40,'title':'one','summary':'sum','revision':1,'settings':Settings().model_dump()})
    body={'start':10,'end':110,'title':'x','summary':'y','settings':Settings().model_dump()}
    assert client.put('/api/clips/'+c['id'],json=body).status_code==400
    body['end']=35
    assert client.put('/api/clips/'+c['id'],json=body).status_code==200
    job=client.post('/api/clips/'+c['id']+'/render').json()
    body['title']='changed'
    client.put('/api/clips/'+c['id'],json=body)
    assert store.get(job['id'])['payload']['clip']['title']=='x'
    assert client.post('/api/clips/'+c['id']+'/render').json()['id']==job['id']


def test_batch_brand_keeps_individual_intro_and_trim():
    client=TestClient(app)
    c=store.create('clip',{'source_id':'test','start':20,'end':50,'title':'a','summary':'b','revision':1,'settings':Settings(intro_text='Lời riêng',crop_x=.3).model_dump()})
    r=client.post('/api/clips/apply-brand',json={'clip_ids':[c['id']],'settings':Settings(watermark_text='KÊNH MỚI',intro_text='Không áp dụng').model_dump()})
    assert r.status_code==200
    changed=store.get(c['id'])
    assert changed['settings']['watermark_text']=='KÊNH MỚI'
    assert changed['settings']['intro_text']=='Lời riêng'
    assert changed['start']==20 and changed['settings']['crop_x']==.3


def test_zoom_allows_reframing_portrait():
    vf=crop_filter({'width':1080,'height':1920},Settings(crop_zoom=1.5,crop_mode='manual',crop_x=.3).model_dump())
    assert vf.startswith('crop=720:1280:')


def test_host_path_maps_to_docker_mount(monkeypatch):
    from unittest.mock import patch
    monkeypatch.setattr(config,'SOURCE_ROOT',Path('/sources'))
    monkeypatch.setenv('SOURCE_DIR','/Users/person/Downloads')
    with patch.object(Path,'is_file',return_value=True), patch.object(Path,'stat') as stat:
        stat.return_value.st_size=100
        assert source_path('/Users/person/Downloads/talk.mp4')==Path('/sources/talk.mp4')
    with pytest.raises(ValueError):source_path('/Users/person/Downloads/../../secret.mp4')


def test_upload_invalid_media_is_actionable_error():
    client=TestClient(app)
    r=client.post('/api/sources/upload',files={'file':('broken.mp4',b'not a valid video','video/mp4')})
    assert r.status_code==400
    assert 'Không đọc được' in r.json()['detail']


def test_polling_omits_large_transcripts_and_job_snapshots():
    source=store.create('source',{'transcript':[{'text':'private raw body'}]})
    clip=store.create('clip',{'words':[{'text':'word'}]})
    job=store.create('job',{'kind':'render','target':clip['id'],'payload':{'large':'snapshot'},'status':'completed','result':{'large':'result'}})
    data=TestClient(app).get('/api/studio').json()
    assert 'transcript' not in next(x for x in data['sources'] if x['id']==source['id'])
    assert 'words' not in next(x for x in data['clips'] if x['id']==clip['id'])
    record=next(x for x in data['jobs'] if x['id']==job['id'])
    assert 'payload' not in record and 'result' not in record


def test_image_watermark_alpha_position(tmp_path):
    from PIL import Image
    path=config.DATA/'assets'/'test-watermark.png'
    Image.new('RGBA',(200,80),(255,255,255,255)).save(path)
    mark=store.create('asset',{'path':str(path.relative_to(config.DATA)),'type':'image'})
    output=tmp_path/'watermark.png'
    watermark_image(Settings(watermark_kind='image',watermark_asset=mark['id'],watermark_x=.5,watermark_y=.5,watermark_scale=.2,watermark_opacity=.5).model_dump(),output)
    image=Image.open(output)
    bounds=image.getbbox()
    assert bounds[2]-bounds[0]==216
    assert abs((bounds[0]+bounds[2])/2-540)<=1
    assert abs((bounds[1]+bounds[3])/2-960)<=1
    assert image.getchannel('A').getextrema()==(0,128)
