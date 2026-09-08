import pytest
from backend.schemas import Settings,CropLock
from backend.static_framing import prepare,at
from backend import presets
from backend.editor import crop_filter
INFO={'width':1920,'height':1080}
TRACK={'start':100,'end':120,'visual_cuts':[5,10,15],'scenes':[],'keyframes':[{'time':0,'x':.2,'face':[.1,.1,.3,.4]},{'time':5,'x':.8,'face':[.7,.1,.9,.4]}]}

def test_static_subject_never_follows_detected_faces():
 s=Settings(crop_mode='manual',crop_x=.8,crop_y=.3,crop_zoom=1.5).model_dump()
 p=prepare(TRACK,INFO,s)
 assert len({(q['x'],q['y']) for q in p['keyframes']})==1
 assert p['keyframes'][0]['x']==.8
 assert p['keyframes'][0]['y']==pytest.approx(1/3)
 assert 'gte(' not in crop_filter(INFO,s,TRACK)

def test_source_absolute_locks_have_exact_boundaries_last_edit_wins():
 s=Settings(crop_mode='manual',crop_x=.2,crop_locks=[CropLock(start=105,end=115,x=.8),CropLock(start=110,end=112,x=.6)]).model_dump()
 assert [at(s,t)['x'] for t in [104.99,105,110,112,115]]==[.2,.8,.6,.8,.2]
 p=prepare(TRACK,INFO,s)
 assert [(q['time'],q['x']) for q in p['keyframes']]==[(0,.2),(5,.8),(10,.6),(12,.8),(15,.2)]
 assert all(q['cut'] for q in p['keyframes'])
 assert 'gte(t,5)' in crop_filter(INFO,s,TRACK)
 # Trimming source-relative locks does not move them to another time in the source.
 trimmed=prepare({**TRACK,'start':108,'end':114,'visual_cuts':[]},INFO,s)
 assert [(q['time'],q['x']) for q in trimmed['keyframes']]==[(0,.8),(2,.6),(4,.8)]

def test_preset_does_not_copy_someone_elses_subject_positions():
 saved=presets.styles(Settings(crop_mode='manual',crop_x=.8,crop_locks=[CropLock(start=0,end=10,x=.8)]).model_dump())
 assert saved['crop_mode']=='manual'
 assert not {'crop_locks','crop_x','crop_y'}&saved.keys()

@pytest.mark.parametrize('data',[{'start':10,'end':5,'x':.5},{'start':0,'end':10,'x':2},{'start':0,'end':10,'x':float('nan')}])
def test_invalid_lock_rejected(data):
 with pytest.raises(ValueError):CropLock(**data)

def test_saved_locks_and_draft_preview_share_exact_geometry(monkeypatch):
 from fastapi.testclient import TestClient
 from backend.app import app
 from backend import store,static_framing
 source=store.create('source',{'duration':120,'width':1920,'height':1080,'path':'unused.mp4'})
 clip=store.create('clip',{'source_id':source['id'],'title':'Static test','start':100,'end':120,'settings':Settings().model_dump(),'revision':1})
 s=Settings(crop_mode='manual',crop_locks=[CropLock(start=105,end=115,x=.8)]).model_dump()
 body={'title':'Static test','summary':'','start':100,'end':120,'settings':s,'words':[]}
 client=TestClient(app)
 assert client.put('/api/clips/'+clip['id'],json=body).status_code==200
 saved=client.get('/api/clips/'+clip['id']).json()
 assert saved['settings']['crop_locks']==s['crop_locks']
 monkeypatch.setattr(static_framing,'cached_track',lambda *args:TRACK)
 response=client.post('/api/clips/'+clip['id']+'/static-framing',json=body)
 assert response.status_code==200
 expected=prepare(TRACK,INFO,s)['keyframes']
 assert response.json()['plan']['keyframes']==expected
