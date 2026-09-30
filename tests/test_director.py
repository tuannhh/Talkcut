import math
import shutil
import subprocess

import numpy as np
import pytest

from backend import director
from backend.director import (FPS, HALF, SINGLE, compose, crop_size, direct, gaps_from_signal, kept_intervals, prepare,
                              punch_jumps, refine_cuts, removals, safe_box, speaker_map, speaking_turns, stack_pair,
                              virtual_camera)

INFO = {'width': 3840, 'height': 2160}


def face(box, person=None, yaw=0.0, score=.9):
    """A face with 5 landmarks whose nose offset gives the requested yaw."""
    x1, y1, x2, y2 = box
    ex = (x2 - x1) * .3
    left, right = (x1 + x2) / 2 - ex / 2, (x1 + x2) / 2 + ex / 2
    ey = y1 + .4 * (y2 - y1)
    nose = (left + right) / 2 + yaw * ex
    return {'box': list(box), 'kps': [[left, ey], [right, ey], [nose, ey + .15 * (y2 - y1)], [left, y2 - .1], [right, y2 - .1]],
            'score': score, 'person': person}


def test_refine_cuts_moves_a_scouted_cut_to_the_changed_frame_on_the_output_grid():
    native = [(i / 25, 1.0) for i in range(150)]
    native[51] = (51 / 25, 40.0)  # the picture changes on source frame 2.04 s
    assert refine_cuts([2.1667], native) == [round(62 / 30, 4)]  # first 30 fps output frame showing it
    assert refine_cuts([3.0], native) == [3.0]  # no clear change nearby: keep the scouted time


def test_people_seen_together_are_never_merged_and_a_later_angle_joins_its_person():
    rng = np.random.default_rng(1)
    base, a, b = (rng.normal(size=512) for _ in range(3))
    person_a, person_b = base + .7 * a / np.linalg.norm(a) * np.linalg.norm(base), base + .7 * b / np.linalg.norm(b) * np.linalg.norm(base)
    assert float(person_a @ person_b / np.linalg.norm(person_a) / np.linalg.norm(person_b)) > director.SAME_PERSON

    def det(box, vector):
        return {'box': box, 'score': .9, 'embedding': (vector + rng.normal(scale=.05, size=512)).tolist()}

    times = [0, .5, 1, 3.5, 4]
    detections = [[det([.2, .3, .3, .5], person_a), det([.7, .3, .8, .5], person_b)] for _ in range(3)]
    detections += [[det([.4, .2, .6, .6], person_a)] for _ in range(2)]
    samples, vectors = director.observations(times, detections, [3.0], 5)
    people = director.cluster(director.tracklets(samples, vectors))
    director.label_people(samples, people)
    left, right = samples[0]['faces'][0]['person'], samples[0]['faces'][1]['person']
    assert left and right and left != right
    assert samples[3]['faces'][0]['person'] == left


def _sample(t, person):
    return {'time': t, 'shot': 0, 'faces': [{'box': [.4, .2, .6, .6], 'person': person}]}


def test_speaker_map_follows_the_camera_and_keeps_voices_one_to_one_per_stt_chunk():
    samples = [_sample(i / 2, 'p0' if i < 20 else 'p1') for i in range(40)]
    samples += [_sample(300 + i / 2, 'p1') for i in range(20)]
    words = [[i, i + .4, 'c0:spk:0'] for i in range(10)] + [[10 + i, 10.4 + i, 'c0:spk:1'] for i in range(10)]
    words += [[300 + i, 300.4 + i, 'c1:spk:0'] for i in range(10)]  # same label, next STT request, other person
    mapping, _ = speaker_map(samples, words)
    assert mapping == {'c0:spk:0': 'p0', 'c0:spk:1': 'p1', 'c1:spk:0': 'p1'}


def test_the_last_voice_takes_the_last_person_when_the_camera_rarely_shows_the_host():
    samples = [_sample(i / 2, 'p1' if i in (30, 31) else 'p0') for i in range(40)]
    words = [[i, i + .4, 'c0:spk:0'] for i in range(8)]
    words += [[t, t + .4, 'c0:spk:1'] for t in (8, 9, 10, 11, 12, 15, 15.5)]  # mostly heard over the guest's face
    mapping, _ = speaker_map(samples, words)
    assert mapping['c0:spk:0'] == 'p0' and mapping['c0:spk:1'] == 'p1'


def test_host_heuristic_picks_the_voice_asking_questions():
    words = []
    for n, (speaker, text) in enumerate([('spk:1', 'Anh nghĩ sao về chuyện này?'), ('spk:0', 'Tôi cho rằng đây là một câu chuyện rất dài và nhiều ý'),
                                          ('spk:1', 'Vậy bước tiếp theo là gì?'), ('spk:0', 'Chúng tôi sẽ tiếp tục đầu tư vào con người và công nghệ')]):
        for i, token in enumerate(text.split()):
            words.append({'start': n * 10 + i * .3, 'end': n * 10 + i * .3 + .25, 'speaker': speaker, 'text': token})
    assert director.host_heuristic(words) == ['c0:spk:1']


def test_virtual_camera_cuts_to_each_new_speaker_but_ignores_short_interjections():
    subjects = [{'person': 'p0', 'height': .2}, {'person': 'p1', 'height': .2}]
    words = [[0, 4, 'a'], [4.5, 8, 'b'], [8.2, 8.6, 'a'], [8.8, 12, 'b']]
    turns = speaking_turns(words, {'a': 'p0', 'b': 'p1'})
    segments = virtual_camera(0, 12, subjects, turns)
    assert [s['subject']['person'] for s in segments] == ['p0', 'p1']
    assert segments[1]['start'] == pytest.approx(4.4)  # just before the new voice, never before the old one ends
    assert segments[1]['start'] * FPS == pytest.approx(round(segments[1]['start'] * FPS))


def test_stacked_pair_puts_the_guest_on_top_and_the_host_below():
    host, guest = {'person': 'p0', 'partial': False, 'height': .2}, {'person': 'p1', 'partial': False, 'height': .2}
    top, bottom = stack_pair([host, guest], {'p0': 'host', 'p1': 'guest'}, [], 0, 5)
    assert (top['person'], bottom['person']) == ('p1', 'p0')
    assert stack_pair([host, {**guest, 'partial': True}], {}, [], 0, 5) is None


def _crop(x, y, size):
    wn, hn = size[0] / INFO['width'], size[1] / INFO['height']
    return x - wn / 2, y - hn / 2, x + wn / 2, y + hn / 2


@pytest.mark.parametrize('box,yaw', [([.07, .3, .11, .44], 1.5), ([.89, .3, .93, .44], -1.5), ([.48, .1, .53, .26], 0),
                                     ([.47, .3, .52, .45], 1.2), ([.3, .5, .36, .7], -.6)])
def test_composition_keeps_the_whole_head_including_the_back_of_a_turned_head(box, yaw):
    obs = [(t, face([box[0] + .004 * t, box[1], box[2] + .004 * t, box[3]], 'p0', yaw)) for t in (0, .5, 1, 1.5)]
    size = crop_size(INFO, SINGLE, box[3] - box[1])
    plan = compose(INFO, obs, [], SINGLE, size, 0)
    for t, f in obs:
        x, y = next((px, py) for pt, px, py in reversed(plan['path']) if pt <= t + 1e-9)
        left, top, right, bottom = _crop(x, y, size)
        s = safe_box(f)
        assert max(0, s[0]) >= left - 1e-6 and min(1, s[2]) <= right + 1e-6
        assert max(0, s[1]) >= top - 1e-6 and min(1, s[3]) <= bottom + 1e-6
    if abs(yaw) >= 1:
        back = box[0] - safe_box(obs[0][1])[0] if yaw > 0 else safe_box(obs[0][1])[2] - box[2]
        assert back >= (box[2] - box[0]) * 1.1  # a profile's skull extends well behind the face box


def test_a_steady_subject_gets_one_locked_window_and_eyes_on_the_upper_third():
    box = [.45, .25, .5, .4]
    obs = [(t / 2, face(box, 'p0')) for t in range(8)]
    size = crop_size(INFO, SINGLE, box[3] - box[1])
    plan = compose(INFO, obs, [], SINGLE, size, 0)
    assert len(plan['path']) == 1
    _, x, y = plan['path'][0]
    top = y - size[1] / INFO['height'] / 2
    eye = (director._eyes(obs[0][1]) - top) / (size[1] / INFO['height'])
    assert abs(eye - SINGLE['eye_line']) < .03


def test_composition_never_leaves_half_of_another_face_at_the_frame_edge():
    box = [.47, .3, .52, .45]
    obs = [(t / 2, face(box, 'p0')) for t in range(4)]
    other = [.60, .3, .66, .45]
    size = crop_size(INFO, SINGLE, box[3] - box[1])
    _, x, y = compose(INFO, obs, [other], SINGLE, size, 0)['path'][0]
    left, _, right, _ = _crop(x, y, size)
    ow = other[2] - other[0]
    lo, hi = other[0] - .1 * ow, other[2] + .1 * ow
    covered = max(0, min(right, hi) - max(left, lo)) / (hi - lo)
    assert covered <= .02 or covered >= .98


def _signal(duration=7.0, rate=16000):
    t = np.arange(int(duration * rate)) / rate
    signal = np.random.default_rng(0).normal(scale=1e-4, size=len(t))

    def tone(a, b, syllables=True):
        m = (t >= a) & (t < b)
        level = .5 * (1 + np.sin(2 * np.pi * 4 * t[m] - np.pi / 2)) if syllables else 1
        signal[m] += .3 * level * np.sin(2 * np.pi * 220 * t[m])

    for a in (0, 2, 4, 6):
        tone(a, a + 1)
    tone(3.2, 3.7, syllables=False)  # "ờ…": one sustained hesitation sound
    tone(5.2, 5.4)
    tone(5.6, 5.8)  # two quick syllables the transcript missed
    return signal.astype(np.float32), rate


def test_pauses_and_fillers_are_tightened_on_quiet_audio_but_missed_speech_is_kept():
    signal, rate = _signal()
    words = [[0, 1, 'a'], [2, 3, 'a'], [4, 5, 'a'], [6, 7, 'a']]
    gaps = gaps_from_signal(signal, rate, words, 7)
    kinds = {(g['start'], g['end']): g['kind'] for g in gaps}
    assert kinds == {(1, 2): 'silent', (3, 4): 'filler', (5, 6): 'speech'}
    speech = next(g for g in gaps if g['kind'] == 'speech')
    assert not speech.get('cut')
    filler = next(g for g in gaps if g['kind'] == 'filler')
    assert filler['cut'][0] <= filler['voiced'][0] and filler['cut'][1] >= filler['voiced'][1]
    removed = removals(gaps)
    assert len(removed) == 2
    for a, b in removed:
        assert abs(a * FPS - round(a * FPS)) < 2e-3 and abs(b * FPS - round(b * FPS)) < 2e-3
        assert not any(a < e and b > s for s, e, _ in words)  # a word is never cut
    assert removals(gaps, enabled=False) == []


def test_kept_intervals_and_jump_punches():
    assert kept_intervals([[1, 1.5]], 3) == [[0, 1], [1.5, 3.0]]
    seg = {'start': 0, 'end': 10, 'layout': 'single'}
    pieces = punch_jumps([seg], [[3, 3.5], [6, 6.5], [9.2, 9.5]])
    assert [(p['start'], p['end'], p['punch'], p['jump']) for p in pieces] == [(0, 3.5, 0, False), (3.5, 6.5, 1, True), (6.5, 10, 0, True)]


def _analysis(stacked_faces=True):
    samples = []
    for i in range(12):
        t = i / 2
        if t < 3:
            faces = [face([.45, .25, .5, .4], 'p0')]
        elif stacked_faces:
            faces = [face([.25, .35, .29, .45], 'p0', .8), face([.72, .35, .76, .45], 'p1', -.8)]
        else:
            faces = [face([.25, .35, .29, .45], 'p0')]
        samples.append({'time': t, 'shot': 0 if t < 3 else 1, 'faces': faces})
    return {'start': 0, 'end': 6, 'visual_cuts': [3.0], 'samples': samples,
            'words': [[0, .9, 'g'], [1.6, 3.3, 'g'], [4.1, 6, 'h']], 'speakers': {'g': 'p0', 'h': 'p1'},
            'cast': [{'id': 'p0', 'role': 'guest', 'speech': 3}, {'id': 'p1', 'role': 'host', 'speech': 2}],
            'gaps': [{'start': .9, 'end': 1.6, 'kind': 'silent', 'cut': [1.0, 1.5]},
                     {'start': 3.3, 'end': 4.1, 'kind': 'silent', 'cut': [3.4, 4.0]}]}


SETTINGS = {'crop_zoom': 1, 'punch_in': True, 'silence_trim': True, 'stacked_enabled': True, 'swap_roles': False, 'mix_seconds': 0}


def test_wide_two_shot_becomes_a_stacked_frame_guest_on_top_and_roles_can_swap():
    plan = prepare(_analysis(), INFO, SETTINGS)
    # The first shot is split at the tightened pause: a punched-in jump cut, same subject.
    assert [s['kind'] for s in plan['scenes']] == ['speaker', 'speaker', 'stacked']
    assert [p['time'] for p in plan['keyframes'] if p.get('jump')] == [1.5]
    assert plan['stacked'][0]['top']['person'] == 'p0' and plan['stacked'][0]['bottom']['person'] == 'p1'
    swapped = prepare(_analysis(), INFO, {**SETTINGS, 'swap_roles': True})
    assert swapped['stacked'][0]['top']['person'] == 'p1'
    assert plan['removed'] == [[1.0, 1.5], [3.4, 4.0]]
    assert plan['kept_duration'] == pytest.approx(4.9)
    assert plan['visual_cuts'] == [3.0]  # jump cuts are not camera cuts
    assert not {'samples', 'words', 'gaps'} & set(plan)
    single = prepare(_analysis(), INFO, {**SETTINGS, 'stacked_enabled': False, 'silence_trim': False})
    assert single['stacked'] == [] and single['removed'] == []
    assert {s['kind'] for s in single['scenes']} <= {'speaker', 'reaction'}


def test_a_face_cut_by_the_frame_edge_is_never_stacked():
    analysis = _analysis()
    for sample in analysis['samples']:
        if sample['shot'] == 1:
            sample['faces'][1] = face([.97, .35, 1.0, .45], 'p1')
    plan = prepare(analysis, INFO, SETTINGS)
    assert plan['stacked'] == []


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='requires a real ffmpeg binary')
def test_export_chain_keeps_picture_and_sound_in_sync_through_jump_cuts(tmp_path):
    """Flashes and beeps at the same source times must still coincide after the
    removed pauses, through the stacked branch, with equal picture/sound length."""
    source = tmp_path / 'src.mkv'
    flash = "between(t,2,2.19)+between(t,4.4,4.59)"
    subprocess.run(['ffmpeg', '-v', 'error', '-y',
                    '-f', 'lavfi', '-i', f"color=black:s=1920x1080:r=25:d=6,drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{flash}'",
                    '-f', 'lavfi', '-i', "aevalsrc='0.5*sin(2*PI*1000*t)*(between(t,2,2.2)+between(t,4.4,4.6))':s=48000:d=6",
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(source)], check=True, timeout=60)
    info = {'width': 1920, 'height': 1080}
    plan = prepare(_analysis(), info, SETTINGS)
    assert plan['stacked']
    vf = director.video_filter(info, SETTINGS, plan)
    af = director.audio_filter(plan['removed'], 6)
    seconds = plan['kept_duration']
    video, audio = tmp_path / 'v.raw', tmp_path / 'a.raw'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '0', '-t', '6', '-i', str(source),
                    # -r 30 as in media.encode_args: otherwise the CLI keeps the 25 fps source rate and drops frames.
                    '-t', str(seconds), '-vf', vf + ',scale=54:96,format=gray', '-an', '-r', '30', '-f', 'rawvideo', str(video),
                    '-t', str(seconds), '-af', af, '-vn', '-ac', '1', '-ar', '48000', '-f', 's16le', str(audio)],
                   check=True, timeout=120)
    frames = np.frombuffer(video.read_bytes(), np.uint8).reshape(-1, 96 * 54).mean(axis=1)
    samples = np.abs(np.frombuffer(audio.read_bytes(), np.int16).astype(np.float32))
    assert len(frames) == round(seconds * FPS)
    assert abs(len(samples) / 48000 - seconds) < 1 / FPS
    bright = frames > 128
    loud = samples > 3000
    starts = [i for i in range(len(bright)) if bright[i] and (i == 0 or not bright[i - 1])]
    beeps = []
    for i in np.flatnonzero(loud):
        if not beeps or i - beeps[-1][1] > 4800:
            beeps.append([i, i])
        beeps[-1][1] = i
    assert [round(s / FPS, 2) for s in starts] == [1.5, 3.3]
    assert len(beeps) == 2
    for s, (a, _) in zip(starts, beeps):
        assert abs(s / FPS - a / 48000) <= 1 / FPS
