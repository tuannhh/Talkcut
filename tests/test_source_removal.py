import pytest
from fastapi.testclient import TestClient

from backend import auth, config, director, focus, store
from backend.app import app

# tests/conftest.py points DATA_DIR at a temporary folder; never touch live data.
assert 'talkcut-tests-' in str(config.DATA)


def make_source(title='Talkshow cũ', size=4096):
    source = store.create('source', {'title': title, 'kind': 'upload', 'status': 'analyzed'})
    folder = config.DATA / 'sources' / source['id']
    folder.mkdir(parents=True)
    (folder / 'original.mp4').write_bytes(b'v' * size)
    (folder / 'transcript.json').write_text('[]')
    return store.update(source['id'], path=f"sources/{source['id']}/original.mp4")


def make_clip(source, start=10.0, end=70.0):
    clip = store.create('clip', {'source_id': source['id'], 'title': 'Đoạn hay', 'start': start, 'end': end, 'settings': {}})
    (config.DATA / 'sources' / source['id'] / f"clip-{clip['id']}.jpg").write_bytes(b'j')
    original = config.DATA / source['path']
    caches = [director.cache_dir(original, clip), focus.cache_dir(original, clip)]
    for cache in caches:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / 'plan.json').write_bytes(b'c' * 100)
    return clip, caches


def make_export(source, clip):
    job = store.create('job', {'kind': 'render', 'target': clip['id'], 'status': 'completed', 'payload': {}})
    folder = config.DATA / 'renders' / job['id']
    folder.mkdir(parents=True)
    (folder / 'final.mp4').write_bytes(b'e' * 2048)
    export = store.create('export', {'clip_id': clip['id'], 'source_id': source['id'], 'title': clip['title'],
                                     'path': f"renders/{job['id']}/final.mp4", 'size': 2048})
    return job, export, folder


def exists(id, kind):
    try:
        store.get(id, kind)
        return True
    except KeyError:
        return False


def test_deleting_a_source_frees_its_files_and_keeps_exported_videos():
    source, other = make_source(), make_source('Nguồn khác')
    clip, caches = make_clip(source)
    other_clip, other_caches = make_clip(other)
    job, export, render = make_export(source, clip)
    analyze = store.create('job', {'kind': 'analyze', 'target': source['id'], 'status': 'completed', 'payload': {}})
    client = TestClient(app)

    usage = client.get(f"/api/sources/{source['id']}/usage").json()
    assert usage['clips'] == 1 and usage['exports'] == 1 and usage['busy'] == 0 and usage['can_delete']
    assert usage['source_bytes'] >= 4096 and usage['cache_bytes'] == 200 and usage['export_bytes'] == 2048

    result = client.delete(f"/api/sources/{source['id']}").json()
    assert result == {'deleted': True, 'freed_bytes': usage['source_bytes'] + 200, 'clips': 1,
                      'exports_deleted': 0, 'exports_kept': 1}
    assert not (config.DATA / 'sources' / source['id']).exists()
    assert not any(c.exists() for c in caches)
    for id, kind in ((source['id'], 'source'), (clip['id'], 'clip'), (job['id'], 'job'), (analyze['id'], 'job')):
        assert not exists(id, kind)
    # The exported video is still listed and playable.
    assert exists(export['id'], 'export') and (render / 'final.mp4').exists()
    # Nothing of the other source was touched.
    assert exists(other['id'], 'source') and exists(other_clip['id'], 'clip')
    assert (config.DATA / other['path']).exists() and all(c.exists() for c in other_caches)


def test_exports_can_be_deleted_with_the_source():
    source = make_source()
    clip, _ = make_clip(source)
    _, export, render = make_export(source, clip)
    result = TestClient(app).delete(f"/api/sources/{source['id']}?exports=delete").json()
    assert result['exports_deleted'] == 1 and result['exports_kept'] == 0
    assert not exists(export['id'], 'export') and not render.exists()


def test_a_source_with_work_in_progress_is_not_deleted():
    source = make_source()
    clip, caches = make_clip(source)
    store.create('job', {'kind': 'focus', 'target': clip['id'], 'status': 'queued', 'payload': {}})
    client = TestClient(app)
    assert client.get(f"/api/sources/{source['id']}/usage").json()['busy'] == 1
    response = client.delete(f"/api/sources/{source['id']}")
    assert response.status_code == 409 and 'tác vụ' in response.json()['detail']
    assert exists(source['id'], 'source') and exists(clip['id'], 'clip')
    assert (config.DATA / source['path']).exists() and all(c.exists() for c in caches)


def test_unknown_source_and_bad_option():
    client = TestClient(app)
    assert client.delete('/api/sources/missing').status_code == 404
    source = make_source()
    assert client.delete(f"/api/sources/{source['id']}?exports=all").status_code == 422
    assert exists(source['id'], 'source')


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(config, 'AUTH_ENABLED', True)
    auth.init()
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE kind='user'")
        db.execute('DELETE FROM sessions')
    auth._failures.clear()
    auth.create_user('admin', 'Quản trị', 'admin-pass-1', 'admin', must_change=False)
    auth.create_user('lan.nt', 'Nguyễn Lan', 'editor-pass-1', 'editor', must_change=False)
    auth.create_user('binh.lt', 'Lê Bình', 'editor-pass-2', 'editor', must_change=False)


def signed_in(username, password):
    client = TestClient(app)
    assert client.post('/api/auth/login', json={'username': username, 'password': password}).status_code == 200
    return client


def test_only_the_owner_or_an_admin_may_delete_a_source(server):
    lan, binh, admin = signed_in('lan.nt', 'editor-pass-1'), signed_in('binh.lt', 'editor-pass-2'), signed_in('admin', 'admin-pass-1')
    owned = {}
    for name, client in (('lan', lan), ('binh', binh)):
        store.actor.set({'id': auth.find(name + ('.nt' if name == 'lan' else '.lt'))['id'], 'name': name})
        owned[name] = make_source(name)
    store.actor.set(None)
    lan_source = owned['lan']
    clip, _ = make_clip(lan_source)
    # Bình rendered a clip of Lan's source: Lan may not delete Bình's video.
    store.actor.set({'id': auth.find('binh.lt')['id'], 'name': 'Lê Bình'})
    _, binh_export, binh_render = make_export(lan_source, clip)
    store.actor.set(None)

    assert binh.get(f"/api/sources/{lan_source['id']}/usage").json()['can_delete'] is False
    assert binh.delete(f"/api/sources/{lan_source['id']}").status_code == 403
    assert exists(lan_source['id'], 'source')

    result = lan.delete(f"/api/sources/{lan_source['id']}?exports=delete").json()
    assert result['exports_deleted'] == 0 and result['exports_kept'] == 1
    assert exists(binh_export['id'], 'export') and binh_render.exists()

    assert admin.delete(f"/api/sources/{owned['binh']['id']}").json()['deleted'] is True
