"""Visual-only pacing: preserve every audio sample and caption timestamp."""
import math
from .focus import prepared_track


def transition_plan(track,info,settings):
    if not track:return {'cuts':[],'holds':[]}
    prepared=prepared_track(track,info,settings)
    holds=prepared['holds']
    cuts=prepared.get('visual_cuts')
    if cuts is None:
        points=prepared['keyframes'];cuts=[q['time'] for p,q in zip(points,points[1:]) if q.get('cut') or q.get('scene')!=p.get('scene')]
    # Holding a reaction removes its entrance cut; the return keeps a short mix.
    cuts=[t for t in cuts if t>0 and not any(h['start']<=t<h['end']-.01 for h in holds)]
    return {'cuts':cuts,'holds':holds}


def visual_filters(plan,seconds):
    from .editor import balanced_sum
    filters=['fps=30:round=up']
    replacement=[h for h in plan['holds'] if h.get('reference') and h.get('path')]
    for i,h in enumerate(replacement):
        from . import config
        path=str(config.DATA/h['path']).replace('\\','\\\\').replace(':','\\:').replace("'","'\\''")
        filters += [f"split[base{i}][unused{i}];[unused{i}]nullsink;movie='{path}',loop=loop=-1:size=1:start=0,setpts=N/30/TB[portrait{i}];[base{i}][portrait{i}]overlay=0:0:enable='gte(t,{h['start']})*lt(t,{h['end']})':shortest=1"]
    ordinary=[h for h in plan['holds'] if not h.get('reference')]
    if ordinary:
        # Drop only the visual frames in a brief insert; fps fills the hole with
        # the last retained image. Original PTS and audio are not shortened.
        expr=balanced_sum([f'gte(t,{h["start"]})*lt(t,{h["end"]})' for h in ordinary])
        filters += [f"select='not({expr})'",'fps=30:round=up']
    if seconds and plan['cuts']:
        windows=mix_windows(plan['cuts'],seconds)
        # Hold the outgoing image and dissolve it into the moving incoming shot.
        # Both branches keep the original PTS: speech and subtitles never shift.
        drop=balanced_sum([f'gte(t,{a})*lt(t,{b})' for a,b in windows])
        # Commands run AFTER the compositor: upstream framesync may prefetch
        # future frames, which would otherwise change opacity too early.
        commands=[]
        for a,b in windows:
            start=max(0,math.ceil(a*30-1e-6)/30-1/30-.00001)
            end=start+b-a
            commands.extend([f'{start:.6f}-{end:.6f} [expr] blend@mix all_opacity 1-TI',f'{end:.6f} blend@mix all_opacity 0'])
        commands=';'.join(commands)
        filters += [f"split[incoming][outgoing];[outgoing]select='not({drop})',fps=30:round=up,tpad=stop_mode=clone:stop_duration=2[held];[held][incoming]blend@mix=all_mode=normal:all_opacity=0:shortest=1,sendcmd=c='{commands}'"]
    return ','.join(filters)


def mix_windows(cuts,seconds):
    times=sorted(set(t for t in cuts if t>0))
    return [(t,round(t+min(seconds,(times[i+1]-t)*.8 if i+1<len(times) else seconds),6)) for i,t in enumerate(times)]
