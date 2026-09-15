import wave
import pytest
from backend.schemas import Settings
from backend.style_templates import StyleProfile, mapped_settings, apply
from backend.editor import make_ass


def profile(**kwargs):
    return StyleProfile(name='Phỏng vấn',summary='Khung đứng yên',composition='Chân dung',mood='Điềm tĩnh',
                        highlights='Tiêu đề đầu',sound='Không chắc',transitions='Mix',**kwargs)


def test_reference_cannot_replace_content_or_select_another_subject(monkeypatch):
    p=profile(caption_font='Barlow',caption_box=True,layout='stacked')
    monkeypatch.setattr('backend.style_templates.store.get',lambda *a:{'status':'ready','profile':p.model_dump()})
    current=Settings(tracking_subject='a'*24,crop_mode='manual',crop_zoom=1.2,intro_text='Lời riêng',watermark_text='Kênh của tôi').model_dump()
    result=apply('template',current)
    assert result['tracking_subject']=='a'*24
    assert result['intro_text']=='Lời riêng' and result['watermark_text']=='Kênh của tôi'
    assert result['caption_font']=='Barlow' and result['caption_box']
    assert result['crop_mode']=='manual' and result['crop_zoom']==1.2 # a style must not discard framing
    assert not {'intro_text','tracking_subject','watermark_text'} & mapped_settings(p).keys()


def test_stacked_layout_enables_the_toggle_but_never_picks_a_subject():
    assert mapped_settings(profile(layout='stacked'))['stacked_enabled'] is True
    assert mapped_settings(profile(layout='mixed'))['stacked_enabled'] is True
    assert mapped_settings(profile(layout='portrait'))['stacked_enabled'] is False
    assert not {'tracking_subject', 'tracking_subject_2'} & mapped_settings(profile(layout='stacked')).keys()


def test_reference_validation_and_failed_profile(monkeypatch):
    for options in ({'caption_font':'../../bad'},{'caption_y':float('nan')},{'mix_seconds':99},{'sound_effect':'shell command'}):
        with pytest.raises(ValueError):profile(**options)
    monkeypatch.setattr('backend.style_templates.store.get',lambda *a:{'status':'failed'})
    with pytest.raises(ValueError):apply('bad',Settings().model_dump())


def test_learned_subtitle_style_keeps_measured_times_and_hook_uses_new_title(tmp_path):
    target=tmp_path/'caption.ass'
    words=[{'start':10.4,'end':10.65,'text':'Xin'},{'start':10.8,'end':11.2,'text':'chào'}]
    settings=Settings(caption_box=True,caption_font='Roboto',caption_karaoke=False,main_title_enabled=True).model_dump()
    make_ass(words,{'start':10,'end':14,'title':'Tiêu đề mới'},settings,target)
    value=target.read_text()
    assert 'Default,Roboto,' in value
    assert 'TIÊU ĐỀ MỚI' in value
    assert '0:00:00.40,0:00:00.65' in value
    assert '\\c&H00FFDF&' not in value
    assert '\\pos(540,960)' in value
    make_ass(words,{'start':0,'end':3},settings,target) # intro has no duplicate hook
    assert 'Dialogue: 1' not in target.read_text()


def test_cues_are_short_original_audio_and_reject_paths(tmp_path,monkeypatch):
    from backend import sound_effects
    monkeypatch.setattr(sound_effects.config,'DATA',tmp_path)
    (tmp_path/'assets').mkdir()
    for kind in ('ding','pop','whoosh'):
        path=sound_effects.cue(kind)
        with wave.open(str(path)) as f:
            assert f.getframerate()==48000 and 0<f.getnframes()/48000<1
        assert sound_effects.cue(kind)==path
    with pytest.raises(ValueError):sound_effects.cue('../../escape')
