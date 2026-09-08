from PIL import Image
from backend import intro_art, editor
from backend.face_tracking import choose_face
from backend.focus import prepared_track
from backend.schemas import Settings


def test_false_small_face_does_not_pull_crop_sideways():
    anchor=[.42,.18,.59,.49]
    assert choose_face([[.425,.26,.50,.39]],anchor)==anchor
    profile=[.43,.18,.60,.49]
    assert choose_face([profile,[.76,.18,.83,.31]],anchor)==profile


def test_fixed_shot_face_jitter_locks_crop():
    track={'start':0,'end':4,'visual_cuts':[], 'keyframes':[
        {'time':i,'x':x,'face':[x-.04,.18,x+.04,.32],'mode':'crop','kind':'speaker'}
        for i,x in enumerate([.80,.81,.795,.805])]}
    p=prepared_track(track,{'width':1920,'height':1080},Settings().model_dump())
    assert len({q['x'] for q in p['keyframes']})==1
    assert p['keyframes'][0]['x']>.75


def test_transparent_portrait_slot_reveals_actual_clip_frame(tmp_path,monkeypatch):
    photo=tmp_path/'freeze.png';Image.new('RGB',(108,192),'#123456').save(photo)
    upload=tmp_path/'template.png';im=Image.new('RGBA',(108,192),(255,255,255,0))
    from PIL import ImageDraw
    ImageDraw.Draw(im).rectangle((0,120,108,192),fill='#0077ff');im.save(upload)
    monkeypatch.setattr(intro_art.store,'get',lambda *args:{})
    monkeypatch.setattr(editor,'asset',lambda id,kind:upload if id=='template' else None)
    monkeypatch.setattr(intro_art,'first_frame',lambda clip:photo)
    s=Settings(intro_image_asset='template',intro_title_enabled=False).model_dump()
    target=tmp_path/'intro.png';intro_art.photo_card(s,target,'',{'id':'same-clip'})
    out=Image.open(target)
    assert out.getpixel((100,100))==(18,52,86)
    assert out.getpixel((100,1800))==(0,119,255)


def test_preview_layers_reconstruct_export_and_styles(tmp_path,monkeypatch):
    photo=tmp_path/'freeze.png';Image.new('RGB',(108,192),'#123456').save(photo)
    monkeypatch.setattr(editor,'asset',lambda *args:None)
    monkeypatch.setattr(intro_art,'first_frame',lambda clip:photo)
    for align in ('left','right','center','justify'):
        s=Settings(intro_title_align=align,intro_title_bold=False,intro_title_italic=True,intro_title_underline=True).model_dump()
        target=tmp_path/(align+'.png');layers=intro_art.photo_card(s,target,'Tiêu đề nhiều từ để kiểm tra định dạng',{})
        base=Image.open(tmp_path/(align+'-base.png')).convert('RGBA')
        ink=Image.open(tmp_path/(align+'-title.png')).convert('RGBA');base.alpha_composite(ink)
        assert base.convert('RGB').tobytes()==Image.open(target).tobytes()
        assert layers and ink.getchannel('A').getbbox()


def test_model_anchor_just_before_native_cut_cannot_sway_outgoing_shot():
    track={'start':0,'end':8,'visual_cuts':[4.0], 'keyframes':[
        {'time':t,'x':x,'face':[x-.04,.18,x+.04,.32],'mode':'crop','kind':'speaker'}
        for t,x in [(0,.8),(1,.81),(2,.80),(3,.805),(3.993,.53),(4.5,.53),(5,.54),(6,.53),(7,.54)]]}
    p=prepared_track(track,{'width':1920,'height':1080},Settings().model_dump())
    assert len({q['x'] for q in p['keyframes'] if q['time']<4})==1
    assert p['keyframes'][0]['x']>.75
