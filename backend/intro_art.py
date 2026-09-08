"""Photo intro: one portrait canvas shared by preview and export."""
import hashlib
import json
import random
import uuid
import threading
_image_lock=threading.RLock()
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
from . import config, store, focus
from .media import ffmpeg, probe


def freeze(source, clip, seconds, target):
    info=probe(source);plan=focus.cached(source,clip)
    crop='scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2'
    if plan:
        points=focus.prepared_track(plan,info,clip['settings'])['keyframes']
        p=next((p for p in reversed(points) if p['time']<=seconds-clip['start']),points[0])
        if p['mode']=='crop':
            x=max(0,min(info['width']-p['cw'],p['x']*info['width']-p['cw']/2))
            y=max(0,min(info['height']-p['ch'],p['y']*info['height']-p['ch']/2))
            crop=f"crop={p['cw']}:{p['ch']}:{x}:{y},scale=1080:1920"
    ffmpeg(['-ss',str(seconds),'-i',source,'-frames:v','1','-vf',crop,target])


def first_frame(clip):
    with _image_lock: return _first_frame(clip)


def _first_frame(clip):
    source=config.DATA/store.get(clip['source_id'],'source')['path']
    key=hashlib.sha256(json.dumps([str(source),clip['start'],clip['end'],'photo-v1']).encode()).hexdigest()[:24]
    directory=config.DATA/'jobs'/('intro-photo-'+key);directory.mkdir(exist_ok=True,parents=True)
    target=directory/'first.jpg'
    if not target.exists():
        temp=directory/'first.tmp.jpg';freeze(source,clip,clip['start'],temp);temp.replace(target)
    return target


def suggestions(clip, refresh=False):
    with _image_lock: return _suggestions(clip,refresh)


def _suggestions(clip, refresh=False):
    key=hashlib.sha256(json.dumps([clip['id'],clip['start'],clip['end']]).encode()).hexdigest()[:24]
    directory=config.DATA/'jobs'/('freeze-'+key);directory.mkdir(exist_ok=True,parents=True)
    saved=directory/'suggestions.json'
    if saved.exists() and not refresh:return json.loads(saved.read_text())
    source=config.DATA/store.get(clip['source_id'],'source')['path'];length=clip['end']-clip['start']
    times=[clip['start'],clip['start']+length*random.uniform(.25,.48),clip['start']+length*random.uniform(.55,.88)]
    items=[]
    for i,t in enumerate(times):
        target=directory/(uuid.uuid4().hex+'.jpg');freeze(source,clip,t,target)
        record=store.create('asset',{'type':'image','name':f'Freeze frame {i+1} · {t:.2f}s','source_time':t,'source_id':clip['source_id'],'path':str(target.relative_to(config.DATA)),'size':target.stat().st_size})
        items.append(record)
    temp=saved.with_suffix('.tmp');temp.write_text(json.dumps(items,ensure_ascii=False));temp.replace(saved)
    return items


def photo_card(settings,target,title,clip):
    from .editor import asset,font,wrap,W,H
    path=asset(settings.get('intro_image_asset'),'image') or first_frame(clip)
    with Image.open(path) as src:
        src=src.convert('RGB');zoom=settings['intro_image_zoom']
        cw=min(src.width,src.height*W/H)/zoom;ch=cw*H/W
        left=(src.width-cw)*settings['intro_image_x'];top=(src.height-ch)*settings['intro_image_y']
        im=src.crop((left,top,left+cw,top+ch)).resize((W,H),Image.Resampling.LANCZOS).convert('RGBA')
    bg=asset(settings.get('intro_asset'),'image') if settings.get('intro_background_enabled') else None
    if bg:
        h=int(H*settings['intro_background_height'])
        with Image.open(bg) as brand:
            banner=ImageOps.contain(brand.convert('RGBA'),(W,h),Image.Resampling.LANCZOS)
            im.paste(Image.new('RGBA',(W,h),'#101114'),(0,0))
            im.alpha_composite(banner,((W-banner.width)//2,(h-banner.height)//2))
    title=(settings.get('intro_title_text') or title) if settings.get('intro_title_enabled') else ''
    if settings['intro_title_case']=='upper':title=title.upper()
    layouts=[]
    if title.strip():
        width=int(W*settings['intro_title_width']);size=settings['intro_title_size']
        while size>28:
            lines=wrap(title,font(size),width-40)
            if len(lines)*size*1.35+40<H*.3:break
            size-=2
        f=font(size);lines=wrap(title,f,width-40);h=int(len(lines)*size*1.35+40)
        x=max(24,min(W-width-24,int(W*settings['intro_title_x']-width/2)))
        y=max(24,min(H-h-24,int(H*settings['intro_title_y']-h/2)))
        shade=Image.new('RGBA',(W,H));d=ImageDraw.Draw(shade)
        d.rounded_rectangle((x,y,x+width,y+h),radius=20,fill=(8,10,14,180));im=Image.alpha_composite(im,shade);d=ImageDraw.Draw(im)
        # Highlight exact whole words selected by the user, matching across wraps.
        highlight={w.casefold().strip('.,!?;:') for w in settings['intro_title_highlight'].split()}
        for row,line in enumerate(lines):
            xx=x+(width-f.getlength(line))/2
            for word in line.split():
                color=settings['intro_title_highlight_color'] if word.casefold().strip('.,!?;:') in highlight else settings['intro_title_color']
                d.text((xx,y+20+row*size*1.35),word,font=f,fill=color,stroke_width=1,stroke_fill='#101114')
                xx+=f.getlength(word+' ')
        layouts.append({'prefix':'intro_title','x':x/W,'y':y/H,'width':width/W,'height':h/H,'size':size})
    im.convert('RGB').save(target)
    return layouts
