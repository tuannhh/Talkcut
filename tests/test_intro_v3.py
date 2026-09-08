import json
import math
import wave
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend import config,store,focus,narration,google_ai
from backend.app import app
from backend.schemas import Settings,VoiceProfile
from backend.voice_profiles import instruction
from backend.editor import intro_card,make_ass


def test_removed_summary_migrates_and_profile_validates():
    assert Settings.model_validate({'summary_enabled':True}).summary_enabled is False
    assert Settings().intro_design=='photo'
    for region in ('bac','trung','nam'):
        p=VoiceProfile(region=region,gender='male',age='trungnien',style='tvc',mood='energetic',speed=1.2)
        text=instruction(p.model_dump())
        assert 'nam' in text and 'trung niên' in text and 'một giọng' in text
    with pytest.raises(ValueError):VoiceProfile(speed=2)


def test_designed_voice_cache_and_deterministic_speed(monkeypatch):
    calls=[]
    def tts(text,voice,path,direction=None):
        calls.append((voice,direction))
        with wave.open(str(path),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
            import struct
            w.writeframes(b''.join(struct.pack('<h',int(8000*math.sin(i*2*math.pi*220/24000))) for i in range(24000)))
    monkeypatch.setattr(google_ai,'tts',tts)
    profile=VoiceProfile(region='trung',gender='male',speed=1.2).model_dump()
    a,_=narration.synthesize('Kiểm tra giọng trung', 'Kore',mode='designed',profile=profile)
    b,_=narration.synthesize('Kiểm tra giọng trung', 'Kore',mode='designed',profile=profile)
    assert a==b and len(calls)==1 and calls[0][0]=='Charon' and 'miền Trung' in calls[0][1]
    from backend.media import probe
    assert .79<probe(a)['duration']<.88
    narration.synthesize('Kiểm tra giọng trung','Kore',mode='designed',profile={**profile,'region':'nam'})
    assert len(calls)==2


def test_alignment_uses_display_tokens_and_rejects_invented_timing(monkeypatch,tmp_path):
    a=tmp_path/'test.wav'
    with wave.open(str(a),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*72000)
    calls=[]
    def gen(prompt,parts):
        calls.append(prompt)
        return {'words':[{'index':0,'start':.1,'end':.3},{'index':1,'start':.35,'end':1.8}]}
    monkeypatch.setattr(google_ai,'generate',gen)
    result=narration.align_display(a,'Năm 2026')
    assert [w['text'] for w in result]==['Năm','2026'] and result[1]['end']==1.8
    assert narration.align_display(a,'Năm 2026')==result and len(calls)==1
    monkeypatch.setattr(google_ai,'generate',lambda *a:{'words':[]})
    with pytest.raises(ValueError):narration.align_display(a,'Văn bản mới')


def test_stable_crop_locks_shot_without_cutting_face():
    info={'width':1920,'height':1080};s=Settings().model_dump()
    raw={'keyframes':[{'time':i/2,'x':.73+(i%2)*.009,'face':[.69+(i%2)*.009,.12,.78+(i%2)*.009,.3],'mode':'crop','scene':'1','kind':'speaker','cut':True} for i in range(20)]}
    p=focus.prepared_track(raw,info,s)['keyframes']
    assert len({v['x'] for v in p})==1
    assert sum(bool(v['cut']) for v in p)==1
    for v in p:
        assert (v['x']*1920-v['cw']/2)/1920<=v['face'][0]
        assert (v['x']*1920+v['cw']/2)/1920>=v['face'][2]


def photo_asset(color):
    a=store.create('asset',{'type':'image','name':'fixture'})
    p=config.DATA/'assets'/(a['id']+'.png');Image.new('RGB',(1080,1920),color).save(p)
    return store.update(a['id'],path=str(p.relative_to(config.DATA)))


def test_photo_intro_no_static_narration_and_highlight(tmp_path):
    a=photo_asset('#203040');s=Settings(intro_image_asset=a['id'],intro_text='KHÔNG HIỆN CẢ ĐOẠN NÀY',intro_title_text='Công nghệ cao',intro_title_highlight='cao',intro_title_highlight_color='#ff7300').model_dump()
    layers=intro_card(s,tmp_path/'intro.png',lambda *a:None,'Khác',{'source_id':'unused'})
    assert len(layers)==1 and layers[0]['prefix']=='intro_title'
    im=Image.open(tmp_path/'intro.png').convert('RGB');assert im.size==(1080,1920)
    assert im.getpixel((10,10))==(32,48,64)
    assert sum(1 for r,g,b in im.getdata() if r>220 and 70<g<155 and b<40)>50


def test_intro_preview_cache_separates_clip_images():
    client=TestClient(app);paths=[]
    for color in ('#123456','#abcdef'):
        a=photo_asset(color);c=store.create('clip',{'source_id':'unused','start':0,'end':10})
        body={'title':'A','summary':'','start':0,'end':10,'settings':Settings(intro_image_asset=a['id']).model_dump()}
        r=client.post('/api/clips/'+c['id']+'/intro-preview',json=body)
        assert r.status_code==200;paths.append(r.json()['path'])
    assert paths[0]!=paths[1]


def test_intro_audio_can_disable_captions_without_alignment(monkeypatch,tmp_path):
    client=TestClient(app);c=store.create('clip',{'source_id':'unused','start':0,'end':10})
    path=config.DATA/'jobs'/'silent.wav'
    with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*24000)
    monkeypatch.setattr(narration,'synthesize',lambda *a:(path,{}))
    monkeypatch.setattr(narration,'align_display',lambda *a:pytest.fail('must not align hidden captions'))
    body={'title':'A','summary':'','start':0,'end':10,'settings':Settings(intro_text='Xin chào',intro_caption_enabled=False).model_dump()}
    r=client.post('/api/clips/'+c['id']+'/intro-audio',json=body)
    assert r.status_code==200 and r.json()['words']==[]


def test_alignment_retries_transient_bad_timestamps(monkeypatch,tmp_path):
    a=tmp_path/'retry.wav'
    with wave.open(str(a),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*24000)
    calls=[]
    def generate(prompt,parts):
        calls.append(prompt)
        return {'words':[{'index':0,'start':.1,'end':2 if len(calls)==1 else .8}]}
    monkeypatch.setattr(google_ai,'generate',generate)
    assert narration.align_display(a,'Chào')[0]['end']==.8
    assert len(calls)==2 and '1.000' in calls[0]
