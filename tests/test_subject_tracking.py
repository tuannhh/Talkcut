import pytest
from backend.schemas import Settings
from backend.subject_tracking import observations,appearance_observations,assemble
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


def test_reference_absence_holds_portrait_including_opening():
    samples=[{'id':0,'shot':0,'time':.5,'face':None},{'id':1,'shot':1,'time':2.5,'face':[.7,.1,.85,.4]},
             {'id':2,'shot':2,'time':4.5,'face':None}]
    track=assemble(samples,[2,4],{'start':100,'end':106},'a'*24)
    assert [(h['start'],h['end'],h['frame_time']) for h in track['reference_holds']]==[(0,2,2.5),(4,6,2.5)]
    plan=prepared_track(track,{'width':1920,'height':1080},Settings(crop_mode='auto',calm_short_shots=False).model_dump())
    assert len(plan['holds'])==2
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


def test_missing_reference_does_not_disable_short_same_voice_holds():
    from backend.focus import calm_holds
    track={'reference_tracking':True,'start':0,'end':12,'visual_cuts':[2,3,8,9],
           'reference_holds':[{'start':8,'end':9,'frame_time':7,'reference':True}],
           'speech_turns':[{'start':0,'end':12,'speaker':'1'}]}
    holds=calm_holds(track,Settings().model_dump())
    assert [(h['start'],h['end']) for h in holds]==[(2,3),(8,9)]
    assert len(calm_holds(track,Settings(calm_short_shots=False).model_dump()))==1


def test_rejected_outlier_cannot_become_replacement_portrait():
    samples=[{'id':i,'shot':0,'time':i+.2,'face':[.7,.1,.8,.3] if i<3 else [.1,.1,.2,.3]} for i in range(4)]
    samples.append({'id':4,'shot':1,'time':4.2,'face':None})
    track=assemble(samples,[4],{'start':0,'end':6},'a'*24)
    assert track['reference_holds'][0]['frame_time']==2.2


def test_arcface_match_requires_a_clear_margin_over_other_faces():
    reference=[1.0]+[0.0]*511
    selected={'box':[.6,.1,.8,.4],'embedding':[.42]+[0.0]*511}
    listener={'box':[.1,.1,.3,.4],'embedding':[.30]+[0.0]*511}
    assert best_match(reference,[listener,selected]) is selected
    # A close second face means the edit must hold a verified portrait rather
    # than switching between interview participants.
    assert best_match(reference,[selected,{**listener,'embedding':[.38]+[0.0]*511}]) is None
