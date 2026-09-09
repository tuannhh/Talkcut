"""Photo intro: one portrait canvas shared by preview and export."""
import hashlib
import json
import random
import uuid
import threading
_image_lock=threading.RLock()
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
from . import config, store, focus
from .media import ffmpeg, probe


def freeze(source, clip, seconds, target):
    info=probe(source)
    if clip['settings'].get('crop_mode')=='manual':
        from .static_framing import cached_track
        plan=cached_track(source,clip)
    else:plan=focus.cached(source,clip)
    crop='scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920'
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
    key=hashlib.sha256(json.dumps([str(source),clip['start'],clip['end'],'photo-v7',clip['settings'].get('crop_mode'),clip['settings'].get('crop_x'),clip['settings'].get('crop_y'),clip['settings'].get('crop_zoom'),clip['settings'].get('crop_locks'),clip['settings'].get('tracking_subject')]).encode()).hexdigest()[:24]
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
    path=asset(settings.get('intro_image_asset'),'image')
    if settings.get('intro_image_asset'):
        record=store.get(settings['intro_image_asset'],'asset')
        if record.get('source_time') is not None and (record.get('source_id')!=clip.get('source_id') or not clip['start']<=record['source_time']<clip['end']):path=None
    # A transparent upload is artwork above a real frame, never an RGB portrait.
    with Image.open(path or first_frame(clip)) as src:
        transparent=src.mode in ('RGBA','LA','P') and src.convert('RGBA').getchannel('A').getextrema()[0]<255
        overlay=src.convert('RGBA').copy() if transparent else None
        photo=Image.open(first_frame(clip)).convert('RGBA') if transparent else src.convert('RGBA')
    zoom=settings['intro_image_zoom']
    cw=min(photo.width,photo.height*W/H)/zoom;ch=cw*H/W
    left=(photo.width-cw)*settings['intro_image_x'];top=(photo.height-ch)*settings['intro_image_y']
    im=photo.crop((left,top,left+cw,top+ch)).resize((W,H),Image.Resampling.LANCZOS)
    if overlay is not None:
        im.alpha_composite(ImageOps.fit(overlay,(W,H),method=Image.Resampling.LANCZOS))
    bg=asset(settings.get('intro_asset'),'image') if settings.get('intro_background_enabled') else None
    if bg:
        with Image.open(bg) as brand:
            brand=brand.convert('RGBA')
            # Uploaded templates may have a transparent upper half. Retain alpha,
            # scale the visible artwork to canvas width and anchor it at the bottom.
            bounds=brand.getchannel('A').getbbox()
            if bounds:
                brand=brand.crop(bounds)
                width=round(W*settings.get('intro_background_scale',1))
                h=round(brand.height*width/brand.width)
                banner=brand.resize((width,h),Image.Resampling.LANCZOS)
                im.alpha_composite(banner,((W-width)//2,H-h))
    base_path=Path(target).with_name(Path(target).stem+'-base.png')
    im.save(base_path)
    ink=Image.new('RGBA',(W,H))
    title=(settings.get('intro_title_text') or title) if settings.get('intro_title_enabled') else ''
    if settings['intro_title_case']=='upper':title=title.upper()
    layouts=[]
    def title_font(size):
        from .title_fonts import title_font as load_font
        return load_font(settings,size)
    if title.strip():
        width=int(W*settings['intro_title_width']);size=settings['intro_title_size']
        while size>28:
            lines=wrap(title,title_font(size),width-40)
            if len(lines)*size*1.35+40<H*.3:break
            size-=2
        f=title_font(size);lines=wrap(title,f,width-40);h=int(len(lines)*size*1.35+40)
        x=max(24,min(W-width-24,int(W*settings['intro_title_x']-width/2)))
        y=max(24,min(H-h-24,int(H*settings['intro_title_y']-h/2)))
        d=ImageDraw.Draw(ink)
        # Highlight exact whole words selected by the user, matching across wraps.
        highlight={w.casefold().strip('.,!?;:') for w in settings['intro_title_highlight'].split()}
        for row,line in enumerate(lines):
            align=settings.get('intro_title_align','center')
            available=width-40;line_width=f.getlength(line)
            xx=x+20+(available-line_width if align=='right' else (available-line_width)/2 if align=='center' else 0)
            extra=(available-line_width)/(len(line.split())-1) if align=='justify' and row<len(lines)-1 and len(line.split())>1 else 0
            for word in line.split():
                color=settings['intro_title_highlight_color'] if word.casefold().strip('.,!?;:') in highlight else settings['intro_title_color']
                d.text((xx,y+20+row*size*1.35),word,font=f,fill=color,stroke_width=1,stroke_fill='#101114')
                if settings.get('intro_title_underline'):
                    yy=y+20+row*size*1.35+f.getbbox(word)[3]+3
                    d.line((xx,yy,xx+f.getlength(word),yy),fill=color,width=max(1,size//22))
                xx+=f.getlength(word+' ')+extra
        layouts.append({'prefix':'intro_title','x':x/W,'y':y/H,'width':width/W,'height':h/H,'size':size})
    ink_path=Path(target).with_name(Path(target).stem+'-title.png')
    ink.save(ink_path)
    im.alpha_composite(ink)
    im.convert('RGB').save(target)
    return layouts
