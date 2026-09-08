import json,subprocess
from pathlib import Path
from PIL import Image
from backend import config,store,focus
from backend.schemas import Settings
from backend.intro_art import photo_card
from backend.transitions import visual_filters,transition_plan


def asset(im,name):
    p=config.DATA/'assets'/name;im.save(p)
    return store.create('asset',{'type':'image','name':name,'path':str(p.relative_to(config.DATA))})['id']


def test_transparent_intro_template_anchors_full_width_at_bottom(tmp_path):
    photo=asset(Image.new('RGB',(108,192),'#663322'),'portrait-v4.png')
    template=Image.new('RGBA',(108,192));template.paste((0,100,220,255),(0,108,108,192))
    bg=asset(template,'brand-v4.png')
    s=Settings(intro_image_asset=photo,intro_asset=bg,intro_background_enabled=True,intro_title_enabled=False).model_dump()
    photo_card(s,tmp_path/'out.png','',{})
    im=Image.open(tmp_path/'out.png')
    assert im.getpixel((20,200))==(102,51,34)
    assert im.getpixel((20,1600))==(0,100,220)
    assert im.getpixel((1060,1600))==(0,100,220)


def test_camera_boundaries_replace_false_chunk_cuts():
    raw={'start':0,'end':6,'visual_cuts':[3.5],'keyframes':[{'time':t,'scene':str(t),'mode':'crop','x':.6,'face':[.55,.1,.65,.3]} for t in (0,.5,1,2,3,3.5,4,5)]}
    p=focus.prepared_track(raw,{'width':1920,'height':1080},Settings().model_dump())
    assert [x['time'] for x in p['keyframes'] if x['cut']]==[0,3.5]
    assert len({x['x'] for x in p['keyframes']})==1


def test_short_reaction_hold_preserves_speaker_shots():
    track={'start':0,'end':8,'visual_cuts':[3,4.5,6],'keyframes':[], 'scenes':[{'start':0,'end':3,'kind':'speaker'},{'start':3,'end':4.5,'kind':'reaction'},{'start':4.5,'end':6,'kind':'speaker'},{'start':6,'end':8,'kind':'speaker'}]}
    p=transition_plan(track,{'width':1920,'height':1080},Settings().model_dump())
    assert p['cuts']==[4.5,6] and len(p['holds'])==1
    assert transition_plan(track,{}, {'calm_short_shots':False})['holds']==[]


def test_mix_only_at_cuts_and_hold_keeps_timeline(tmp_path):
    # Red → brief blue listener → green. Keep original 3-second timeline.
    graph="color=red:s=64x64:r=30:d=1[r];color=blue:s=64x64:r=30:d=1[b];color=green:s=64x64:r=30:d=1[g];[r][b][g]concat=n=3:v=1:a=0,"+visual_filters({'holds':[{'start':1,'end':2}],'cuts':[2]},.2)+",format=rgb24[out]"
    r=subprocess.run(['ffmpeg','-v','error','-filter_complex',graph,'-map','[out]','-f','rawvideo','-'],capture_output=True,check=True)
    frames=[r.stdout[i:i+64*64*3] for i in range(0,len(r.stdout),64*64*3)]
    assert len(frames)==90
    pixel=lambda i:tuple(frames[i][:3])
    assert pixel(15)[0]>240 and pixel(45)[0]>240 # hold did not introduce blue
    assert 20<pixel(62)[0]<230 and pixel(62)[1]>10 # actual mixed transition
    assert pixel(75)[0]<10 and pixel(75)[1]>100 # crisp after transition


def test_native_cut_refinement_uses_original_frame_precision(tmp_path):
    original=tmp_path/'original.mp4';proxy=tmp_path/'shots-0.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:s=160x90:r=25:d=0.96','-f','lavfi','-i','color=blue:s=160x90:r=25:d=1','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0','-c:v','libx264',str(original)],check=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(original),'-vf','fps=6','-c:v','libx264',str(proxy)],check=True)
    result={};focus.visual_layout(tmp_path,result,original,{'start':0,'end':1.96})
    assert result['source_fps']==25
    assert abs(result['visual_cuts'][0]-.96)<.001
