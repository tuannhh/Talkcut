"""Small original synthesized cues; no reference audio is reused."""
import math
import random
import struct
import wave
import threading
from . import config

_lock=threading.Lock()


def cue(kind):
    with _lock:return _cue(kind)


def _cue(kind):
    if kind not in ('pop','ding','whoosh'):raise ValueError('Hiệu ứng âm thanh không hợp lệ.')
    folder=config.DATA/'assets';target=folder/f'talkcut-cue-v1-{kind}.wav'
    if target.exists():return target
    rate=48000;duration={'pop':.16,'ding':.7,'whoosh':.45}[kind];rng=random.Random(17)
    values=[];smooth=0
    for i in range(round(rate*duration)):
        t=i/rate
        if kind=='ding':v=(math.sin(2*math.pi*880*t)+.25*math.sin(2*math.pi*1760*t))*math.exp(-9*t)
        elif kind=='pop':v=math.sin(2*math.pi*(450*t-850*t*t))*math.exp(-28*t)
        else:
            smooth=.8*smooth+.2*rng.uniform(-1,1)
            v=smooth*math.sin(math.pi*t/duration)**2*3
        envelope=min(1,t/.008)*min(1,(duration-t)/.02)
        values.append(struct.pack('<h',round(max(-1,min(1,v*envelope))*.16*32767)))
    temp=target.with_suffix('.tmp')
    with wave.open(str(temp),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(b''.join(values))
    temp.replace(target)
    return target
