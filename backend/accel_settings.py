"""User-controlled override for GPU/CPU render acceleration.

A tiny singleton record in the same generic store as everything else
(kind='accel_settings'). Missing record == 'auto', matching the env-level
default in config.py. This is read fresh on every render call (see
media.py), so flipping it in the UI takes effect on the *next* render with
no container restart — unlike the face-engine's execution-provider choice,
which is fixed for the lifetime of its worker pool.
"""
from . import store

MODES = ('auto', 'cuda', 'cpu')


def get():
    rows = store.listing('accel_settings')
    return rows[0] if rows else {'render_accel': 'auto'}


def set_render_accel(mode):
    if mode not in MODES:
        raise ValueError('Chế độ không hợp lệ. Chọn auto, cuda hoặc cpu.')
    current = get()
    if 'id' in current:
        return store.update(current['id'], render_accel=mode)
    return store.create('accel_settings', {'render_accel': mode})
