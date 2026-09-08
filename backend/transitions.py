"""Visual-only pacing: preserve every audio sample and caption timestamp."""
import math
from .focus import prepared_track


def transition_plan(track,info,settings):
    if not track:return {'cuts':[],'holds':[]}
    prepared=prepared_track(track,info,settings)
    holds=prepared['holds']
    cuts=track.get('visual_cuts')
    if cuts is None:
        points=prepared['keyframes'];cuts=[q['time'] for p,q in zip(points,points[1:]) if q.get('cut') or q.get('scene')!=p.get('scene')]
    # Holding a reaction removes its entrance cut; the return keeps a short mix.
    cuts=[t for t in cuts if t>0 and not any(h['start']<=t<h['end']-.01 for h in holds)]
    return {'cuts':cuts,'holds':holds}


def visual_filters(plan,seconds):
    from .editor import balanced_sum
    filters=['fps=30:round=up']
    if plan['holds']:
        # Drop only the visual frames in a brief insert; fps fills the hole with
        # the last retained image. Original PTS and audio are not shortened.
        expr=balanced_sum([f'gte(t,{h["start"]})*lt(t,{h["end"]})' for h in plan['holds']])
        filters += [f"select='not({expr})'",'fps=30:round=up']
    if seconds and plan['cuts']:
        frames=max(2,round(seconds*30));duration=frames/30
        active=balanced_sum([f'gte(t,{t})*lt(t,{t+duration:.6f})' for t in plan['cuts']])
        # tmix's disabled path can return older timestamps in FFmpeg. Always
        # feed its buffer and gate the overlay, keeping the clean stream's PTS.
        filters += [f"split[clean][mixinput];[mixinput]tmix=frames={frames}:weights='1'[mixed];[clean][mixed]overlay=enable='{active}':eof_action=pass"]
    return ','.join(filters)
