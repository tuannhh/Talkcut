import json
import subprocess
import threading

import pytest

from backend import google_ai, pipeline


@pytest.fixture
def source(tmp_path, monkeypatch):
    """12 s video: 6 s of digital silence (a livestream waiting screen), then a tone."""
    path = tmp_path / 'talk.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=64x36:d=12',
                    '-f', 'lavfi', '-i', r'aevalsrc=if(lt(t\,6)\,0\,0.4*sin(2*PI*440*t)):s=16000:d=12',
                    '-shortest', '-c:v', 'libx264', '-c:a', 'aac', str(path)], check=True)
    monkeypatch.setattr(pipeline, 'STT_CHUNK', 4)
    folder = tmp_path / 'stt'
    folder.mkdir()
    return {'id': 'src', 'path': str(path), 'duration': 12.0}, folder


def fake_stt(calls, answers=None):
    lock = threading.Lock()

    def transcribe(audio):
        index = int(audio.stem.split('-')[1])
        with lock:
            calls.append(index)
        if answers and index in answers:
            return answers[index](calls.count(index))
        return [{'text': f'từ{index}', 'start': 2.5, 'end': 3.0, 'speaker': 'a'}]
    return transcribe


def test_silent_chunk_is_skipped_not_fatal_and_words_keep_source_time(source, monkeypatch):
    src, folder = source
    calls = []
    monkeypatch.setattr(google_ai, 'transcribe', fake_stt(calls))
    words, gaps = pipeline.transcribe_source(src, folder, lambda *a: None)
    assert 0 not in calls  # the silent first chunk never reaches Google
    assert sorted(calls) == [1, 2]
    assert [w['text'] for w in words] == ['từ1', 'từ2']
    # chunk 1 audio starts at 4 - 2 s overlap = 2 s; measured offsets are kept, never estimated
    assert words[0]['start'] == pytest.approx(4.5) and words[1]['start'] == pytest.approx(8.5)
    assert gaps == []
    assert json.loads((folder / 'words-0.json').read_text()) == []  # cached: a retry does not re-measure


def test_audible_chunk_without_words_is_retried_once_then_reported_as_a_gap(source, monkeypatch):
    src, folder = source
    calls = []
    monkeypatch.setattr(google_ai, 'transcribe', fake_stt(calls, {2: lambda n: []}))
    words, gaps = pipeline.transcribe_source(src, folder, lambda *a: None)
    assert calls.count(2) == 2
    assert [w['text'] for w in words] == ['từ1']
    assert gaps == [[6.0, 12.0]]
    assert not (folder / 'words-2.json').exists()  # asked again on the next analysis


def test_failed_chunk_keeps_finished_chunks_cached(source, monkeypatch):
    src, folder = source
    calls = []

    def boom(n):
        raise google_ai.AIError('mạng lỗi')
    monkeypatch.setattr(google_ai, 'transcribe', fake_stt(calls, {1: boom}))
    with pytest.raises(google_ai.AIError):
        pipeline.transcribe_source(src, folder, lambda *a: None)
    assert (folder / 'words-2.json').exists() and not (folder / 'words-1.json').exists()
    calls.clear()
    monkeypatch.setattr(google_ai, 'transcribe', fake_stt(calls))
    words, _ = pipeline.transcribe_source(src, folder, lambda *a: None)
    assert calls == [1]  # only the missing chunk is requested again
    assert [w['text'] for w in words] == ['từ1', 'từ2']


def test_source_without_any_speech_still_fails_clearly(source, monkeypatch):
    src, folder = source
    monkeypatch.setattr(google_ai, 'transcribe', lambda audio: [])
    with pytest.raises(google_ai.AIError, match='mốc thời gian'):
        pipeline.transcribe_source(src, folder, lambda *a: None)
