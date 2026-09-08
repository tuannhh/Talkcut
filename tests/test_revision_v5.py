import subprocess
from fastapi.testclient import TestClient
from backend.app import app
from backend.schemas import Settings
from backend import store, focus
from backend.transitions import visual_filters,mix_windows


def test_presets_persist_styles_without_replacing_clip_content():
    client=TestClient(app)
    origin=Settings(intro_text='Lời dẫn clip cũ',intro_title_text='Tiêu đề cũ',intro_title_highlight='cũ',intro_image_asset='old-photo',intro_frame_time=55,caption_size=80,mix_seconds=.9).model_dump()
    response=client.post('/api/presets',json={'name':'Kênh thử','settings':origin})
    assert response.status_code==200,response.text
    preset=response.json();id=preset['id']
    assert all(k not in preset['settings'] for k in ('intro_text','intro_image_asset','intro_frame_time','intro_title_text','intro_title_highlight'))
    current=Settings(intro_text='Lời dẫn mới',intro_title_text='Tiêu đề mới',intro_image_asset='new-photo',intro_frame_time=22).model_dump()
    applied=client.post(f'/api/presets/{id}/apply',json=current).json()['settings']
    assert applied['caption_size']==80 and applied['mix_seconds']==.9
    assert applied['intro_text']=='Lời dẫn mới' and applied['intro_image_asset']=='new-photo' and applied['intro_frame_time']==22
    assert any(p['id']==id for p in client.get('/api/presets').json())
    response=client.put(f'/api/presets/{id}',json={'name':'Kênh cập nhật','settings':{**origin,'caption_size':72}})
    assert response.json()['settings']['caption_size']==72
    assert client.delete(f'/api/presets/{id}').status_code==200
    assert client.post(f'/api/presets/{id}/apply',json=current).status_code==404


def test_preset_cannot_overwrite_another_record_kind():
    client=TestClient(app);source=store.create('source',{'title':'keep'})
    assert client.put('/api/presets/'+source['id'],json={'name':'bad','settings':{}}).status_code==404
    assert client.delete('/api/presets/'+source['id']).status_code==404
    assert store.get(source['id'])['title']=='keep'
    assert client.post('/api/presets',json={'name':'   ','settings':{}}).status_code==400


def test_saved_v4_migrates_once_and_new_mix_can_be_disabled():
    assert Settings.model_validate({'crop_mode':'auto','transition_seconds':.24}).mix_seconds==.65
    assert Settings.model_validate({'crop_mode':'auto','mix_seconds':0,'pacing_version':5}).mix_seconds==0
    assert Settings(mix_seconds=1.2).mix_seconds==1.2


def test_vertical_crop_uses_visible_face_even_for_uncertain_shot():
    raw={'start':0,'end':2,'visual_cuts':[],'keyframes':[{'time':t,'scene':0,'mode':'fit','x':.8,'kind':'uncertain','face':[.73,.1,.86,.3]} for t in (0,.5,1)]}
    plan=focus.prepared_track(raw,{'width':1920,'height':1080},Settings().model_dump())
    assert all(p['mode']=='crop' and p['x']>.7 for p in plan['keyframes'])


def test_mix_near_end_does_not_shorten_clip_and_windows_do_not_overlap():
    windows=mix_windows([1,1.4,2.8],1.2)
    assert windows[0][1]<windows[1][0]
    graph='color=red:s=32x32:r=30:d=2.8[r];color=blue:s=32x32:r=30:d=0.2[b];[r][b]concat=n=2:v=1:a=0,'+visual_filters({'holds':[],'cuts':[2.8]},.65)+',format=rgb24[out]'
    r=subprocess.run(['ffmpeg','-v','error','-filter_complex',graph,'-map','[out]','-f','rawvideo','-'],capture_output=True,check=True)
    assert len(r.stdout)==90*32*32*3
    first=tuple(r.stdout[84*32*32*3:84*32*32*3+3]);last=tuple(r.stdout[-32*32*3:-32*32*3+3])
    assert first[0]>230 and last[0]>100 and last[2]>20


def test_short_angle_hold_does_not_hide_a_voice_change():
    track={'start':0,'end':10,'source_fps':25,'visual_cuts':[3,5,8], 'scenes':[], 'speech_turns':[{'start':0,'end':8,'speaker':'A'}]}
    assert focus.calm_holds(track,Settings().model_dump())[0]['start']==3
    track['speech_turns']=[{'start':0,'end':3,'speaker':'A'},{'start':3,'end':5,'speaker':'B'},{'start':5,'end':10,'speaker':'A'}]
    assert focus.calm_holds(track,Settings().model_dump())==[]


def test_new_mix_settings_remain_readable_by_legacy_v4_range():
    current=Settings(mix_seconds=1.2).model_dump()
    assert current['transition_seconds']<=.5 and current['mix_seconds']==1.2
    upgraded=Settings.model_validate({'pacing_version':5,'transition_seconds':.9})
    assert upgraded.mix_seconds==.9 and upgraded.transition_seconds==.24
