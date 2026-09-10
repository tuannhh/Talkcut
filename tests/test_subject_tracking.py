import pytest
from backend.schemas import Settings
from backend.subject_tracking import observations,appearance_observations,assemble,_gallery_times,_gallery_cache,cached_candidates
from backend.focus import prepared_track,cache_dir
from backend.presets import styles
from backend.title_fonts import title_font
from backend.face_engine import best_match


def test_reference_rejects_wrong_ids_missing_and_low_confidence():
    samples=[{'id':0,'shot':0,'time':.5},{'id':1,'shot':0,'time':1}]
    raw={'observations':[{'id':99,'visible':True,'confidence':1,'face':[.1,.1,.2,.3]},
                         {'id':0,'visible':True,'confidence':.4,'face':[.1,.1,.2,.3]},
                         {'id':1,'visible':True,'confidence':.95,'face':[.72,.1,.85,.38]}]}
    result=observations(raw,samples)
    assert result[0]['face'] is None
    assert result[1]['face'][0]==.72


def test_reference_uses_only_local_face_selected_by_appearance():
    samples=[{'id':0,'faces':[[.1,.1,.2,.3],[.7,.1,.8,.3]]}, {'id':1,'faces':[[.4,.1,.5,.3]]}]
    raw={'matches':[{'id':0,'visible':True,'candidate':1,'confidence':.95},
                    {'id':1,'visible':True,'candidate':4,'confidence':.99},
                    {'id':2,'visible':True,'candidate':0,'confidence':.99}]}
    result=appearance_observations(raw,samples)
    assert result[0]['face']==[.7,.1,.8,.3]
    assert result[1]['face'] is None


def test_reference_stays_on_right_in_wide_and_recenters_in_closeup():
    samples=[{'id':i,'shot':i//2,'time':t,'face':box} for i,(t,box) in enumerate([
      (.5,[.75,.12,.84,.34]),(1.5,[.755,.12,.845,.34]),
      (2.5,[.42,.12,.62,.5]),(3.5,[.425,.12,.625,.5])])]
    track=assemble(samples,[2],{'start':100,'end':104},'a'*24)
    plan=prepared_track(track,{'width':1920,'height':1080},Settings(crop_mode='auto').model_dump())
    assert plan['keyframes'][0]['x']>.7
    assert .4<plan['keyframes'][2]['x']<.65
    assert plan['keyframes'][0]['x']==plan['keyframes'][1]['x']
    assert plan['keyframes'][2]['x']==plan['keyframes'][3]['x']
    assert plan['visual_cuts']==[2]


def test_reference_absence_keeps_moving_source_video_including_opening():
    samples=[{'id':0,'shot':0,'time':.5,'face':None},{'id':1,'shot':1,'time':2.5,'face':[.7,.1,.85,.4]},
             {'id':2,'shot':2,'time':4.5,'face':None}]
    track=assemble(samples,[2,4],{'start':100,'end':106},'a'*24)
    assert track['reference_holds']==[]
    assert [(h['start'],h['end'],h['anchor_time']) for h in track['dynamic_fallbacks']]==[(0,2,2.5),(4,6,2.5)]
    plan=prepared_track(track,{'width':1920,'height':1080},Settings(crop_mode='auto',calm_short_shots=False).model_dump())
    assert plan['holds']==[]
    assert all(p['x']>.7 for p in plan['keyframes'])
    with pytest.raises(ValueError):assemble([{'shot':0,'face':None}],[],{'start':0,'end':3},'a'*24)


def test_reference_cannot_transfer_through_preset_or_path_injection(tmp_path):
    s=Settings(tracking_subject='a'*24,intro_title_font='Barlow').model_dump()
    assert 'tracking_subject' not in styles(s)
    assert styles(s)['intro_title_font']=='Barlow'
    with pytest.raises(ValueError):Settings(tracking_subject='../escape')
    source=tmp_path/'source.mp4';source.write_bytes(b'x')
    base={'start':0,'end':5,'settings':{}}
    assert cache_dir(source,base)!=cache_dir(source,{**base,'settings':s})


@pytest.mark.parametrize('family',['Google Sans','Open Sans','Barlow','Roboto'])
@pytest.mark.parametrize('bold,italic',[(False,False),(True,False),(False,True),(True,True)])
def test_bundled_fonts_load_vietnamese(family,bold,italic):
    f=title_font({'intro_title_font':family,'intro_title_bold':bold,'intro_title_italic':italic},60)
    assert f.getlength('Quản trị doanh nghiệp – Ưu đãi thuế')>500
    assert f.getmask('ắ ề ộ ự Đ').getbbox()


def test_selected_draft_uses_auto_geometry_even_when_saved_manual(monkeypatch):
    import backend.app as api
    c={'source_id':'source','start':0,'end':2,'settings':Settings(crop_mode='manual').model_dump()}
    monkeypatch.setattr(api.store,'get',lambda id,*args: c if id=='clip' else {'path':'source.mp4','width':1920,'height':1080})
    monkeypatch.setattr('backend.subject_tracking.reference',lambda *args: {})
    seen=[]
    monkeypatch.setattr(api.focusing,'cached',lambda source,clip: seen.append(clip['settings']) or None)
    monkeypatch.setattr(api.focusing,'visual_preview',lambda *args: pytest.fail('Opening a clip must not scan the whole video'))
    assert api.get_focus('clip',zoom=1,subject='a'*24)['plan'] is None
    assert seen[0]['crop_mode']=='auto'
    assert c['settings']['crop_mode']=='manual'


def test_focus_endpoint_keeps_ordinary_reaction_hold_support(tmp_path,monkeypatch):
    """Removing reference stills must not break unrelated focus responses."""
    import backend.app as api
    source_file=tmp_path/'source.mp4';source_file.write_bytes(b'x')
    clip={'id':'clip','source_id':'source','start':0,'end':2,'settings':Settings(crop_mode='auto').model_dump()}
    source={'path':str(source_file), 'width':1920, 'height':1080}
    track={'start':0,'end':2,'keyframes':[{'time':0,'x':.5,'mode':'crop','scene':'camera:0'}], 'visual_cuts':[], 'scenes':[]}
    monkeypatch.setattr(api.store,'get',lambda id,*args: clip if id=='clip' else source)
    monkeypatch.setattr(api.focusing,'cached',lambda *args: track)
    monkeypatch.setattr(api.focusing,'prepared_track',lambda *args: {**track,'holds':[{'start':.5,'end':.8,'frame_time':.4}]})
    monkeypatch.setattr(api.focusing,'calm_holds',lambda *args: [{'start':.5,'end':.8,'frame_time':.4}])
    hold_dir=api.config.DATA/'ordinary-hold';hold_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(api.focusing,'cache_dir',lambda *args: hold_dir)
    monkeypatch.setattr('backend.intro_art.freeze',lambda source,clip,seconds,target: target.write_bytes(b'jpg'))
    result=api.get_focus('clip', None)
    assert result['plan']['holds'][0]['path'].endswith('.jpg')


def test_reference_tracking_never_inserts_a_static_visual_hold():
    from backend.focus import calm_holds
    track={'reference_tracking':True,'start':0,'end':12,'visual_cuts':[2,3,8,9],
           'reference_holds':[{'start':8,'end':9,'frame_time':7,'reference':True}],
           'keyframes':[{'time':0,'x':.5,'mode':'crop','scene':'camera:0'}],
           'speech_turns':[{'start':0,'end':12,'speaker':'1'}]}
    assert calm_holds(track,Settings().model_dump())==[]
    assert calm_holds(track,Settings(calm_short_shots=False).model_dump())==[]
    from backend.transitions import transition_plan, visual_filters
    plan=transition_plan(track,{'width':1920,'height':1080},Settings().model_dump())
    assert plan['holds']==[]
    assert 'movie=' not in visual_filters(plan,.65)


def test_rejected_outlier_keeps_a_dynamic_last_confirmed_crop():
    samples=[{'id':i,'shot':0,'time':i+.2,'face':[.7,.1,.8,.3] if i<3 else [.1,.1,.2,.3]} for i in range(4)]
    samples.append({'id':4,'shot':1,'time':4.2,'face':None})
    track=assemble(samples,[4],{'start':0,'end':6},'a'*24)
    assert track['reference_holds']==[]
    assert track['dynamic_fallbacks'][0]['anchor_time']==2.2


def test_arcface_match_requires_a_clear_margin_over_other_faces():
    reference=[1.0]+[0.0]*511
    selected={'box':[.6,.1,.8,.4],'embedding':[.42]+[0.0]*511}
    listener={'box':[.1,.1,.3,.4],'embedding':[.30]+[0.0]*511}
    assert best_match(reference,[listener,selected]) is selected
    # A close second face means the edit must abstain rather than switch
    # between interview participants.
    assert best_match(reference,[selected,{**listener,'embedding':[.38]+[0.0]*511}]) is None


def test_gallery_samples_are_limited_to_the_selected_clip_and_cache_is_read_only(tmp_path):
    clip={'id':'clip','start':100,'end':160}
    times=_gallery_times(clip)
    assert len(times)==9
    assert all(100 <= item < 160 for item in times)
    directory=tmp_path/'subjects';directory.mkdir()
    cache=_gallery_cache(directory,clip)
    cache.write_text('[{"id":"a","path":"subjects/a.jpg"}]')
    assert cached_candidates(tmp_path/'source.mp4',clip)==[{"id":"a","path":"subjects/a.jpg"}]


def test_subject_gallery_scan_is_persistent_queue_work(monkeypatch):
    import backend.app as api
    monkeypatch.setattr(api.store,'get',lambda id,*args: {'id':id})
    seen=[]
    monkeypatch.setattr(api.pipeline,'enqueue',lambda kind,target,payload: seen.append((kind,target,payload)) or {'kind':kind,'target':target})
    assert api.scan_subject_gallery('clip')=={'kind':'subject-gallery','target':'clip'}
    assert seen==[('subject-gallery','clip',{'refresh':False})]
