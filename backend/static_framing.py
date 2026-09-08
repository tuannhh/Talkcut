"""User-directed, piecewise constant framing. No inferred camera motion."""
import json
from . import focus


def cached_track(source, clip):
    path=focus.cache_dir(source,clip)/'focus.json'
    if path.exists():return json.loads(path.read_text())
    return {'start':clip['start'],'end':clip['end'],'keyframes':[], 'visual_cuts':[], 'scenes':[]}


def at(settings, absolute_time):
    selected=next((r for r in reversed(settings.get('crop_locks',[])) if r['start']<=absolute_time<r['end']),None)
    return {'x':selected['x'] if selected else settings.get('crop_x',.5),
            'y':selected['y'] if selected else settings.get('crop_y',.5)}


def prepare(track,info,settings):
    start,end=track['start'],track['end'];duration=end-start
    cuts={t for t in track.get('visual_cuts',[]) if 0<t<duration}
    for r in settings.get('crop_locks',[]):
        cuts.update(t-start for t in (r['start'],r['end']) if start<t<end)
    times=[0,*sorted(cuts)];points=[]
    for i,t in enumerate(times):
        center=at(settings,start+t)
        p=focus.geometry(info,settings,center)
        points.append({**p,'time':t,'cut':True,'scene':f'locked:{i}','kind':'uncertain'})
    return {**track,'keyframes':points,'visual_cuts':sorted(cuts),'prepared':True,
            'prepared_zoom':settings.get('crop_zoom',1),'holds':focus.calm_holds(track,settings),
            'note':'Khóa vị trí do bạn chọn. Khung crop không tự di chuyển.'}
