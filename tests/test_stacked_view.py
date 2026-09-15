import shutil
import subprocess
import pytest
from backend.schemas import Settings
from backend.stacked_view import wide_two_shot, half_geometry, assemble, wrap, cache_dir


def test_wide_two_shot_needs_two_small_separated_faces():
    wide_left, wide_right = [.1, .2, .3, .45], [.62, .2, .82, .45]
    assert wide_two_shot(wide_left, wide_right)
    assert wide_two_shot(wide_right, wide_left)
    assert not wide_two_shot(wide_left, None)
    close_up = [.3, .1, .75, .6]
    assert not wide_two_shot(close_up, wide_right)  # a close-up face is too large for a wide two-shot
    overlapping = [.55, .2, .78, .45]
    assert not wide_two_shot(wide_right, overlapping)  # not separated enough to be two distinct people


def test_half_geometry_centers_a_tight_bust_crop_and_stays_in_frame():
    info = {'width': 1920, 'height': 1080}
    g = half_geometry(info, Settings().model_dump(), [.05, .1, .2, .3])
    assert g['cw'] > 0 and g['ch'] > 0
    assert abs(g['ch'] / g['cw'] - 8 / 9) < .02  # even-pixel rounding, not an exact ratio
    assert g['cw'] / 2 / info['width'] <= g['x'] <= 1 - g['cw'] / 2 / info['width']
    assert g['ch'] / 2 / info['height'] <= g['y'] <= 1 - g['ch'] / 2 / info['height']


def test_assemble_only_keeps_shots_with_confident_paired_faces_long_enough():
    clip = {'start': 0, 'end': 12}
    samples = [
        {'time': .5, 'top': [.1, .1, .3, .35], 'bottom': [.6, .1, .8, .35]},
        {'time': 1.5, 'top': [.11, .1, .31, .35], 'bottom': [.61, .1, .81, .35]},
        {'time': 4.5, 'top': None, 'bottom': None},  # close-up shot: no pairing
        {'time': 8.5, 'top': [.1, .1, .3, .35], 'bottom': None},  # only one face confirmed
    ]
    result = assemble(samples, [3, 7], clip, 'a' * 24, 'b' * 24)
    assert [seg['start'] for seg in result['segments']] == [0]
    assert result['segments'][0]['top'] == 'a' * 24 and result['segments'][0]['bottom'] == 'b' * 24
    assert len(result['segments'][0]['box_top']) == 4


def test_assemble_drops_a_window_shorter_than_the_minimum_duration():
    clip = {'start': 0, 'end': 10}
    samples = [{'time': .3, 'top': [.1, .1, .3, .35], 'bottom': [.6, .1, .8, .35]}]
    result = assemble(samples, [.8], clip, 'a' * 24, 'b' * 24, min_duration=1.0)
    assert result['segments'] == []


def test_cache_dir_changes_with_either_subject_token(tmp_path):
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'x')
    clip = {'start': 0, 'end': 5}
    base = cache_dir(source, clip, 'a' * 24, 'b' * 24)
    assert base != cache_dir(source, clip, 'c' * 24, 'b' * 24)
    assert base != cache_dir(source, clip, 'a' * 24, 'd' * 24)


def test_wrap_is_a_no_op_without_segments():
    assert wrap('scale=1080:1920', [], {'width': 1920, 'height': 1080}, Settings().model_dump()) == 'scale=1080:1920'


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='requires a real ffmpeg binary')
def test_stacked_composite_shows_both_halves_with_a_seam_only_inside_the_window():
    info = {'width': 1920, 'height': 1080}
    settings = Settings().model_dump()
    segments = [{'start': 1.0, 'end': 2.0, 'top': 'a' * 24, 'bottom': 'b' * 24,
                 'box_top': [.02, .1, .3, .5], 'box_bottom': [.7, .1, .98, .5]}]
    # The base graph paints solid red everywhere so we can tell "outside window" from "stacked".
    # testsrc (not a flat color) gives the two face crops different content to compare.
    vf = wrap('scale=1080:1920,drawbox=c=red:t=fill', segments, info, settings)
    graph = f'testsrc=size=1920x1080:rate=30:duration=3,{vf},format=rgb24[out]'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-filter_complex', graph, '-map', '[out]',
                         '-t', '3', '-f', 'rawvideo', '-'], capture_output=True, check=True)
    frame_bytes = 1080 * 1920 * 3
    assert len(r.stdout) == 90 * frame_bytes

    def pixel(frame_index, x, y):
        offset = frame_index * frame_bytes + (y * 1080 + x) * 3
        return tuple(r.stdout[offset:offset + 3])

    outside = pixel(0, 540, 960)
    assert outside[0] > 150 and outside[1] < 100  # still the plain red base graph, no overlay
    inside_top = pixel(45, 540, 200)
    inside_bottom = pixel(45, 540, 1700)
    assert inside_top != inside_bottom  # two different crops, not a duplicated frame
    seam = pixel(45, 540, 960)
    assert seam != inside_top and seam != inside_bottom  # the gradient band is visible at the seam


def test_scan_endpoint_requires_both_subjects_and_enqueues_persistent_work(monkeypatch):
    import backend.app as api
    clip_missing = {'id': 'clip', 'settings': Settings(tracking_subject='a' * 24).model_dump()}
    monkeypatch.setattr(api.store, 'get', lambda id, *args: clip_missing)
    with pytest.raises(ValueError):
        api.scan_stacked('clip')
    clip_ready = {'id': 'clip', 'settings': Settings(tracking_subject='a' * 24, tracking_subject_2='b' * 24).model_dump()}
    monkeypatch.setattr(api.store, 'get', lambda id, *args: clip_ready)
    seen = []
    monkeypatch.setattr(api.pipeline, 'enqueue', lambda kind, target, payload: seen.append((kind, target, payload)) or {'kind': kind, 'target': target})
    assert api.scan_stacked('clip') == {'kind': 'stacked-view', 'target': 'clip'}
    assert seen == [('stacked-view', 'clip', {})]


def test_get_stacked_reads_cache_without_triggering_detection(tmp_path, monkeypatch):
    import backend.app as api
    clip = {'id': 'clip', 'source_id': 'source', 'start': 0, 'end': 5,
            'settings': Settings(tracking_subject='a' * 24, tracking_subject_2='b' * 24).model_dump()}
    source = {'path': 'source.mp4'}
    monkeypatch.setattr(api.store, 'get', lambda id, *args: clip if id == 'clip' else source)
    directory = tmp_path / 'stacked-cache'
    directory.mkdir()
    (directory / 'stacked.json').write_text('{"segments": [{"start": 1, "end": 2}]}')
    monkeypatch.setattr('backend.stacked_view.cache_dir', lambda src, c, t, b: directory)
    assert api.get_stacked('clip')['segments'] == [{'start': 1, 'end': 2}]
    monkeypatch.setattr(api.store, 'get', lambda id, *args: {**clip, 'settings': Settings().model_dump()})
    assert api.get_stacked('clip')['segments'] is None
