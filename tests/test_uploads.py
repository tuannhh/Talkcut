import subprocess

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module, auth, config, store
from backend.app import app

assert 'talkcut-tests-' in str(config.DATA)


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'talk.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=2', '-f', 'lavfi',
                    '-i', 'sine=frequency=300:duration=2', '-shortest', '-c:v', 'libx264', '-c:a', 'aac', str(path)], check=True)
    return path.read_bytes()


def test_large_source_arrives_in_pieces_and_resumes_where_it_stopped(video, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_CHUNK', 4096)
    client = TestClient(app)
    started = client.post('/api/uploads', json={'name': 'Talkshow tháng 10.mp4', 'size': len(video)}).json()
    id, chunk = started['id'], started['chunk_size']
    assert chunk == 4096
    assert client.put(f'/api/uploads/{id}?offset=0', content=video[:chunk]).json() == {'received': chunk}
    # A retried piece (network dropped after the server stored it) is answered with the real position.
    retry = client.put(f'/api/uploads/{id}?offset=0', content=video[:chunk])
    assert retry.status_code == 409 and retry.json()['received'] == chunk
    assert client.post(f'/api/uploads/{id}/complete').status_code == 400  # not all there yet
    # The browser comes back later and asks where to continue.
    received = client.get(f'/api/uploads/{id}').json()['received']
    while received < len(video):
        received = client.put(f'/api/uploads/{id}?offset={received}', content=video[received:received + chunk]).json()['received']
    source = client.post(f'/api/uploads/{id}/complete').json()
    assert source['status'] == 'ready' and source['title'] == 'Talkshow tháng 10.mp4'
    assert (config.DATA / source['path']).read_bytes() == video
    assert not app_module.upload_part(id).exists()
    with pytest.raises(KeyError):
        store.get(id, 'upload')


def test_uploads_reject_oversized_pieces_wrong_types_and_too_large_files(monkeypatch):
    client = TestClient(app)
    assert client.post('/api/uploads', json={'name': 'notes.txt', 'size': 10}).status_code == 400
    monkeypatch.setattr(config, 'MAX_BYTES', 100)
    assert client.post('/api/uploads', json={'name': 'big.mp4', 'size': 101}).status_code == 413
    id = client.post('/api/uploads', json={'name': 'a.mp4', 'size': 50}).json()['id']
    assert client.put(f'/api/uploads/{id}?offset=0', content=b'x' * 60).status_code == 400  # beyond the declared size
    monkeypatch.setattr(app_module, 'UPLOAD_CHUNK', 10)
    assert client.put(f'/api/uploads/{id}?offset=0', content=b'x' * 11).status_code == 413


def test_someone_elses_upload_cannot_be_continued(monkeypatch):
    monkeypatch.setattr(config, 'AUTH_ENABLED', True)
    auth.init()
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE kind='user'")
    auth._failures.clear()
    for name in ('an.tv', 'binh.lt'):
        auth.create_user(name, name, 'pass-word-1', must_change=False)
    an, binh = TestClient(app), TestClient(app)
    an.post('/api/auth/login', json={'username': 'an.tv', 'password': 'pass-word-1'})
    binh.post('/api/auth/login', json={'username': 'binh.lt', 'password': 'pass-word-1'})
    id = an.post('/api/uploads', json={'name': 'a.mp4', 'size': 10}).json()['id']
    assert binh.put(f'/api/uploads/{id}?offset=0', content=b'x').status_code == 403
    assert binh.get(f'/api/uploads/{id}').status_code == 403
    assert an.put(f'/api/uploads/{id}?offset=0', content=b'x').status_code == 200
