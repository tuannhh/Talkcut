import json
import subprocess
from pathlib import Path

import pytest

from backend import config, pipeline, store

assert 'talkcut-tests-' in str(config.DATA)


def video(width, height, seconds=3):
    item = store.create('source', {'title': 'proxy test', 'status': 'importing'})
    path = config.DATA / 'sources' / item['id'] / 'original.mp4'
    path.parent.mkdir(parents=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=s={width}x{height}:d={seconds}:r=25',
                    '-f', 'lavfi', '-i', f'sine=frequency=300:duration={seconds}', '-shortest',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-g', '250', '-c:a', 'aac', str(path)], check=True)
    return item, path


def keyframes(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-skip_frame', 'nokey', '-show_entries',
                          'frame=pts_time:stream=width,height', '-of', 'json', str(path)], capture_output=True, check=True)
    data = json.loads(out.stdout)
    return (data['streams'][0]['width'], data['streams'][0]['height']), [float(f['pts_time']) for f in data['frames']]


@pytest.mark.parametrize('info,suffix,expected', [
    ({'width': 3840, 'height': 2160, 'codec': 'h264'}, '.mp4', True),
    ({'width': 1920, 'height': 1080, 'codec': 'av1'}, '.mp4', True),
    ({'width': 1920, 'height': 1080, 'codec': 'h264'}, '.mov', True),
    ({'width': 1920, 'height': 1080, 'codec': 'h264'}, '.mp4', False),
    # A vertical phone recording is still 1080p class: no proxy.
    ({'width': 1080, 'height': 1920, 'codec': 'h264'}, '.mp4', False),
    ({'width': 2160, 'height': 3840, 'codec': 'h264'}, '.mp4', True),
])
def test_only_sources_office_browsers_play_poorly_get_a_preview_copy(monkeypatch, info, suffix, expected):
    monkeypatch.setattr(config, 'PREVIEW_PROXY', 'auto')
    assert pipeline.needs_proxy(info, Path('original' + suffix)) is expected
    monkeypatch.setattr(config, 'PREVIEW_PROXY', 'off')
    assert pipeline.needs_proxy(info, Path('original' + suffix)) is False


@pytest.mark.parametrize('size,expected', [((2560, 1440), (1920, 1080)), ((1440, 2560), (1080, 1920))])
def test_preview_copy_keeps_orientation_and_seeks_every_second(monkeypatch, size, expected):
    monkeypatch.setattr(config, 'PREVIEW_PROXY', 'auto')
    monkeypatch.setattr(pipeline, 'enqueue', lambda kind, target, *a, **k: {'kind': kind, 'target': target})
    item, path = video(*size)
    source = pipeline.finish_source(item, path)
    assert source['preview_path'] == source['path']  # the original plays until the copy is ready
    result = pipeline.make_proxy(source, lambda *a: None)
    preview = config.DATA / result['preview_path']
    assert store.get(item['id'], 'source')['preview_path'] == result['preview_path']
    assert (config.DATA / source['path']).exists()  # analysis and export keep the original
    (width, height), keys = keyframes(preview)
    assert (width, height) == expected
    assert keys[:3] == pytest.approx([0, 1, 2], abs=0.05)
