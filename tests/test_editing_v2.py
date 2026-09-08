import json
import math
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import config, store, narration, focus
from backend.app import app
from backend.schemas import Settings
from backend.tts_normalizer import normalize, year, quantity, DICTIONARY
from backend.editor import crop_filter, intro_card

@pytest.mark.parametrize('text,expected',[
 ('năm 2026','năm hai không hai sáu'),('năm 1994','năm một chín chín tư'),('năm 2004','năm hai lẻ tư'),('năm 1903','năm một chín linh ba'),('năm 1804','năm một tám linh tư'),('năm 2005','năm hai lẻ năm'),('năm 2015','năm hai không một lăm'),
 ('117/2025','một một bảy hai không hai lăm'),('18/2026/NĐ-CP','mười tám hai không hai sáu nờ đê xê pê'),('Số 18/2026/NĐ-CP','Số mười tám hai không hai sáu nờ đê xê pê'),
 ('43.000','bốn mươi ba nghìn'),('43000','bốn mươi ba nghìn'),('1.234.567','một triệu hai trăm ba mươi tư nghìn năm trăm sáu mươi bảy'),('1.005','một nghìn không trăm linh năm'),('21','hai mươi mốt'),('24','hai mươi tư'),('25','hai mươi lăm'),('104','một trăm linh tư'),('105','một trăm linh năm'),
 ('23,7','hai ba phẩy bảy'),('12,05','một hai phẩy không năm'),('0,25','không phẩy hai năm'),
 ('03/04/2026','mùng ba tháng tư năm hai không hai sáu'),('ngày 15/04/2026','ngày mười lăm tháng tư năm hai không hai sáu'),('tháng 03/2026','tháng ba năm hai không hai sáu'),
 ('Doanh thu +20%.','Doanh thu tăng hai mươi phần trăm.'),('Biên lợi nhuận -23,7%.','Biên lợi nhuận giảm hai ba phẩy bảy phần trăm.'),('- 20% doanh thu','hai mươi phần trăm doanh thu'),('20-30%','hai mươi đến ba mươi phần trăm'),('3–5 ngày','ba đến năm ngày'),('giai đoạn 1994–2026','giai đoạn một chín chín tư đến hai không hai sáu'),
 ('8 AM','tám giờ sáng'),('8 PM','tám giờ tối'),('08:30','tám giờ ba mươi phút'),('8h00-12h00','tám giờ đến mười hai giờ'),
 ('Video dùng tỷ lệ 16:9. Bài toán có phân số 1/2. Hạn chót là 01/02/2026.','Video dùng tỷ lệ mười sáu trên chín. Bài toán có phân số một phần hai. Hạn chót là mùng một tháng hai năm hai không hai sáu.'),
 ('điện thoại 0901234567','điện thoại không chín không một hai ba bốn năm sáu bảy'),('1.000.000đ','một triệu đồng'),('25.000 VNĐ','hai mươi lăm nghìn đồng'),
 ('Năm 2026, doanh nghiệp đặt mục tiêu 2026 khách hàng.','Năm hai không hai sáu, doanh nghiệp đặt mục tiêu hai nghìn không trăm hai mươi sáu khách hàng.'),
 ('TB Pháp chế đã tăng năng suất cho mỗi người trong ban TB 300%','Trưởng ban Pháp chế đã tăng năng suất cho mỗi người trong ban trung bình ba trăm phần trăm'),
 ('AMIS, EMIS, Jetpay, MISA Corp, MISA JSC','A mít, E mít, Dét Pây, Tập đoàn MISA, Công ty Cổ phần MISA'),('GĐVP, TNHH MTV, QHĐT, ĐHCĐ','Giám đốc Văn phòng, Trách nhiệm hữu hạn một thành viên, Quan hệ đối tác, Đại hội cổ đông'),
 ('Ai chịu trách nhiệm? AI hỗ trợ, ít dữ liệu cho IT. Demo.','Ai chịu trách nhiệm? AI hỗ trợ, ít dữ liệu cho IT. Demo.'),
 ('Chào mừng bạn đến với công cụ cắt video tự động bằng AI của MISA','Chào mừng bạn đến với công cụ cắt video tự động bằng AI của MISA'),
])
def test_reference_readings(text,expected):
    result=normalize(text)
    assert result['tts_text']==expected
    assert result['source_text']==result['display_text']==text
    assert not result['requires_review'],result['warnings']
    assert normalize(text)==result
    for s in result['spans']:assert text[s['start']:s['end']]==s['original']

@pytest.mark.parametrize('text',['TB đã trao đổi','03/2026','XYZ','1.23.456','31/02/2026','0901234567','AM','N03-T1','https://example.com/?a=AMIS&b=2026','v1.2.3','`+20% AMIS`'])
def test_ambiguous_or_protected_never_silently_rewritten(text):
    result=normalize(text)
    assert result['requires_review']
    assert result['tts_text']==text


def test_all_approved_mapping_longest_match_and_boundaries():
    for key,spoken in DICTIONARY['entries'].items():
        assert normalize(key,context_tags=['business_internal'])['tts_text']==spoken
    assert normalize('ABCDN01')['tts_text']=='ABCDN01'
    result=normalize('8 AM. AM phụ trách khách hàng')
    assert result['tts_text']=='tám giờ sáng. A em phụ trách khách hàng'


def test_tts_gate_invalidates_when_script_or_version_changes(monkeypatch):
    calls=[]
    monkeypatch.setattr(narration.google_ai,'tts',lambda text,voice,path:(calls.append(text),path.write_bytes(b'RIFFtest')))
    with pytest.raises(ValueError):narration.synthesize('TB đang nói','Kore')
    assert not calls
    approved=narration.approve('TB đang nói','Trưởng ban đang nói')
    path,plan=narration.synthesize('TB đang nói','Kore',approved['id'])
    assert calls==['Trưởng ban đang nói'] and path.exists()
    narration.synthesize('TB đang nói','Kore',approved['id'])
    assert len(calls)==1
    with pytest.raises(ValueError):narration.synthesize('TB đang nghe','Kore',approved['id'])
    with pytest.raises(ValueError):narration.synthesize('Xin chào','UnknownVoice')


def test_focus_abstains_and_fills_missing_scenes():
    raw=[{'start':1,'end':3,'kind':'speaker','visible_speaking':True,'confidence':.9,'keyframes':[{'time':1,'face':[.65,.1,.8,.35]}]}, {'start':3,'end':4,'kind':'speaker','visible_speaking':False,'confidence':.95,'keyframes':[{'time':3,'face':[.1,.1,.3,.4]}]}]
    scenes=focus.sanitize(raw,5)
    assert [(s['start'],s['end'],s['kind']) for s in scenes]==[(0,1,'uncertain'),(1,3,'speaker'),(3,4,'uncertain'),(4,5,'uncertain')]
    assert focus.sanitize([{'start':float('nan'),'end':5,'kind':'speaker','confidence':.99,'visible_speaking':True,'keyframes':[]}],5)[0]['kind']=='uncertain'


def test_face_headroom_geometry_and_fit_when_too_large():
    info={'width':1920,'height':1080};settings=Settings().model_dump()
    p={'x':.78,'face':[.69,.12,.85,.35],'mode':'crop'}
    g=focus.geometry(info,settings,p)
    left=(g['x']*1920-g['cw']/2)/1920;right=left+g['cw']/1920
    assert g['mode']=='crop' and left<=.69 and right>=.85
    huge=focus.geometry(info,settings,{'x':.5,'face':[.2,.05,.8,.8],'mode':'crop'})
    assert huge['mode']=='fit'
    assert focus.geometry(info,settings,{'x':.78,'mode':'fit'})['mode']=='fit'


def test_scene_change_jumps_and_broll_fit_does_not_trim_audio():
    track={'start':10,'end':20,'keyframes':[{'time':0,'x':.75,'face':[.7,.1,.8,.3],'mode':'crop','scene':0},{'time':3,'x':.2,'face':[.15,.1,.25,.3],'mode':'crop','scene':1,'cut':True},{'time':5,'x':.5,'mode':'fit','scene':2}]}
    vf=crop_filter({'width':1920,'height':1080},Settings().model_dump(),track)
    assert 'gte(t,3)' in vf and 'overlay' in vf and 'gte(t,5)*lt(t,10)' in vf
    assert 'trim' not in vf and 'select=' not in vf


def test_long_focus_plan_parses_in_real_ffmpeg_without_dropping_points():
    import shutil
    import subprocess
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg is required for the long-clip integration check')
    track = {'start': 0, 'end': 600, 'keyframes': [
        {'time': i / 2, 'x': .25 + (i % 13) / 26,
         'mode': 'fit' if i % 4 == 0 else 'crop', 'scene': i // 20}
        for i in range(1200)
    ]}
    vf = crop_filter({'width': 1920, 'height': 1080}, Settings().model_dump(), track)
    assert '599.0' in vf
    result = subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                             'color=s=1920x1080:d=0.1', '-frames:v', '1',
                             '-vf', vf, '-f', 'null', '-'], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()


def test_old_settings_migrate_without_overwriting_values():
    old={'intro_text':'Lời đã viết','watermark_x':.74,'crop_mode':'manual','intro_voice':'Aoede'}
    settings=Settings.model_validate(old).model_dump()
    assert settings['intro_text']=='Lời đã viết' and settings['watermark_x']==.74
    assert settings['intro_title_enabled'] and settings['intro_title_case']=='original'


def test_intro_two_layers_render_at_separate_positions(tmp_path):
    from PIL import Image
    settings=Settings(intro_text='Một lời mở đầu',intro_y=.25,intro_title_y=.7,intro_title_case='upper',intro_color='#ffcc00').model_dump()
    target=tmp_path/'intro.png';intro_card(settings,target,lambda *a:None,'Tiêu đề clip')
    image=Image.open(target)
    assert image.size==(1080,1920)
    bg=image.getpixel((1,1))
    assert image.getpixel((540,480))!=bg and image.getpixel((540,1344))!=bg


def test_normalizer_api_and_no_key_leak():
    client=TestClient(app)
    response=client.post('/api/tts/normalize',json={'text':'năm 2026 +20%'}).json()
    assert response['tts_text']=='năm hai không hai sáu tăng hai mươi phần trăm'
    assert client.post('/api/tts/normalize',json={'text':'x'*2001}).status_code==422
    assert 'Kore' in client.get('/api/voices').json()['voices']
    assert client.post('/api/tts/preview',json={'voice':'invalid','text':'abc'}).status_code==400


def test_user_pronunciation_cannot_override_structural_time_or_code():
    result=normalize('8 AM, AMIS. `AMIS`',overrides={'AM':'A em','AMIS':'A mít khác'})
    assert result['tts_text']=='tám giờ sáng, A mít khác. `AMIS`'


def test_fuzz_normalization_trace_and_quantity_invariants():
    import random,unicodedata
    rng=random.Random(74)
    for _ in range(150):
        n=rng.randrange(0,10**12)
        spoken=quantity(n)
        assert spoken and not any(c.isdigit() for c in spoken)
        source=f'Năm 2026 có {n} khách hàng.'
        result=normalize(source)
        previous=0
        for span in result['spans']:
            assert span['start']>=previous and span['end']>span['start']
            assert source[span['start']:span['end']]==span['original']
            previous=span['end']
        assert result['display_text']==source
    for punct in ['/', '-', '+', '−', '–', '—', ':', '.', '%']:
        normalize(f'12{punct}34 và 23,7%')
    source=unicodedata.normalize('NFD','Thuế doanh nghiệp')
    result=normalize(source)
    assert result['source_text']==source
    assert result['tts_text']==unicodedata.normalize('NFC',source)


def test_new_script_approval_survives_save_and_stale_approval_is_cleared():
    client=TestClient(app)
    s=store.create('source',{'duration':100})
    c=store.create('clip',{'source_id':s['id'],'start':0,'end':10,'title':'A','summary':'B','revision':1,'settings':Settings(intro_text='Cũ').model_dump()})
    approved=narration.approve('TB Pháp chế','Trưởng ban Pháp chế')
    settings=Settings(intro_text='TB Pháp chế',intro_approval_id=approved['id']).model_dump()
    payload={'title':'A','summary':'B','start':0,'end':10,'settings':settings}
    saved=client.put('/api/clips/'+c['id'],json=payload).json()
    assert saved['settings']['intro_approval_id']==approved['id']
    payload['settings']['intro_text']='Mới'
    saved=client.put('/api/clips/'+c['id'],json=payload).json()
    assert saved['settings']['intro_approval_id'] is None


def test_intro_preview_uses_same_renderer_and_safe_bounds():
    client=TestClient(app)
    c=store.create('clip',{'source_id':'unused','start':0,'end':10})
    body={'title':'Tiêu đề thử','summary':'','start':0,'end':10,'settings':Settings(intro_text='Một lời mở đầu '*35,intro_x=.9,intro_y=.8).model_dump()}
    response=client.post('/api/clips/'+c['id']+'/intro-preview',json=body)
    assert response.status_code==200
    result=response.json()
    assert len(result['layers'])==2
    assert (config.DATA/result['path']).is_file()
    for layer in result['layers']:
        assert 0<=layer['x']<layer['x']+layer['width']<=1
        assert 0<=layer['y']<layer['y']+layer['height']<=1


def test_intro_auto_layout_reserves_entire_logo_and_platform_safe_area():
    from backend.editor import fit_intro_regions, font, wrap
    settings=Settings(intro_text='Làm thế nào để xây dựng năng lực nghiên cứu và phát triển cho doanh nghiệp?',intro_title_case='upper').model_dump()
    title='Chiến lược R&D và bài toán ưu đãi thuế công nghệ cao'
    layout=fit_intro_regions(settings,title,[[.25,.565,.98,.66]])
    for prefix,text in [('intro',settings['intro_text']),('intro_title',title.upper())]:
        size=layout[prefix+'_size'];width=layout[prefix+'_width']*1080
        height=(len(wrap(text,font(size),int(width)-40))*size*1.35+40)/1920
        top=layout[prefix+'_y']-height/2;bottom=top+height
        assert top>=.119 and bottom<=.831
        assert bottom<=.546 or top>=.679
