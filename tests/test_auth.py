import pytest
from fastapi.testclient import TestClient
from backend import auth, config, pipeline, store
from backend.app import app

# tests/conftest.py points DATA_DIR at a temporary folder; never touch live data.
assert 'talkcut-tests-' in str(config.DATA)
from backend.schemas import Settings


@pytest.fixture
def server(monkeypatch):
    """Server edition: accounts on, a clean user/session table and login counters."""
    monkeypatch.setattr(config, 'AUTH_ENABLED', True)
    auth.init()
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE kind IN ('user', 'preset')")
        db.execute('DELETE FROM sessions')
    auth._failures.clear()
    admin = auth.create_user('admin', 'Quản trị', 'admin-pass-1', 'admin', must_change=False)
    editor = auth.create_user('lan.nt', 'Nguyễn Lan', 'editor-pass-1', 'editor', must_change=False)
    return admin, editor


def signed_in(username, password):
    client = TestClient(app)
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200, response.text
    return client


def test_personal_install_needs_no_login():
    assert TestClient(app).get('/api/auth/me').json() == {'auth_enabled': False, 'user': None}
    assert TestClient(app).get('/api/studio').status_code == 200


def test_everything_but_login_requires_a_session(server):
    client = TestClient(app)
    assert client.get('/api/studio').status_code == 401
    assert client.get('/media/sources/x/original.mp4').status_code == 401
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/auth/me').json() == {'auth_enabled': True, 'user': None}


def test_login_sets_an_httponly_cookie_and_only_its_hash_is_stored(server):
    client = TestClient(app)
    response = client.post('/api/auth/login', json={'username': ' Admin ', 'password': 'admin-pass-1'})
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Secure' not in cookie
    token = client.cookies[auth.COOKIE]
    with store.connect() as db:
        stored = [r['token_hash'] for r in db.execute('SELECT token_hash FROM sessions')]
    assert token not in stored and len(stored) == 1
    assert 'admin-pass-1' not in str(store.listing('user'))
    assert client.get('/api/studio').status_code == 200
    assert client.get('/api/auth/me').json()['user']['display_name'] == 'Quản trị'
    assert 'password_hash' not in client.get('/api/auth/me').json()['user']
    client.post('/api/auth/logout')
    assert client.get('/api/studio').status_code == 401


def test_cookie_is_secure_behind_an_https_proxy(server):
    response = TestClient(app).post('/api/auth/login', json={'username': 'admin', 'password': 'admin-pass-1'},
                                    headers={'X-Forwarded-Proto': 'https'})
    assert 'Secure' in response.headers['set-cookie']


def test_repeated_wrong_passwords_are_slowed_down(server):
    client = TestClient(app)
    for _ in range(auth.MAX_FAILURES):
        assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong-pass'}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin-pass-1'}).status_code == 429
    # Unknown names answer like wrong passwords (no account discovery).
    assert client.post('/api/auth/login', json={'username': 'ghost', 'password': 'x' * 8}).json()['detail'] == \
        'Tên đăng nhập hoặc mật khẩu chưa đúng.'


def test_records_remember_who_made_them_and_only_owner_or_admin_may_delete(server):
    admin, editor = server
    lan = signed_in('lan.nt', 'editor-pass-1')
    preset = lan.post('/api/presets', json={'name': 'Kênh MISA', 'settings': Settings().model_dump()}).json()
    assert preset['created_by'] == {'id': editor['id'], 'name': 'Nguyễn Lan'}
    other = signed_in('admin', 'admin-pass-1').post('/api/presets', json={'name': 'Của quản trị', 'settings': Settings().model_dump()}).json()
    assert lan.delete('/api/presets/' + other['id']).status_code == 403
    assert lan.delete('/api/presets/' + preset['id']).status_code == 200
    assert signed_in('admin', 'admin-pass-1').delete('/api/presets/' + other['id']).status_code == 200


def test_only_admins_manage_accounts_and_new_users_must_change_their_password(server):
    admin_client = signed_in('admin', 'admin-pass-1')
    lan = signed_in('lan.nt', 'editor-pass-1')
    assert lan.get('/api/users').status_code == 403
    assert lan.post('/api/accel', json={'render_accel': 'cpu'}).status_code == 403
    created = admin_client.post('/api/users', json={'username': 'minh.pv', 'display_name': 'Phạm Minh', 'password': 'temp-pass-1'}).json()
    assert created['role'] == 'editor' and created['must_change_password'] is True
    minh = signed_in('minh.pv', 'temp-pass-1')
    assert minh.get('/api/studio').status_code == 403
    assert minh.post('/api/auth/password', json={'current_password': 'temp-pass-1', 'new_password': 'short'}).status_code == 400
    assert minh.post('/api/auth/password', json={'current_password': 'temp-pass-1', 'new_password': 'minh-own-pass'}).status_code == 200
    assert minh.get('/api/studio').status_code == 200
    # Locking an account ends its sessions at once.
    assert admin_client.put('/api/users/' + created['id'], json={'active': False}).status_code == 200
    assert minh.get('/api/studio').status_code == 401
    assert TestClient(app).post('/api/auth/login', json={'username': 'minh.pv', 'password': 'minh-own-pass'}).status_code == 401


def test_the_last_active_admin_cannot_be_removed(server):
    admin, editor = server
    admin_client = signed_in('admin', 'admin-pass-1')
    assert admin_client.put('/api/users/' + admin['id'], json={'role': 'editor'}).status_code == 400
    assert admin_client.put('/api/users/' + editor['id'], json={'role': 'admin'}).status_code == 200
    assert admin_client.put('/api/users/' + admin['id'], json={'active': False}).status_code == 400  # not yourself
    lan = signed_in('lan.nt', 'editor-pass-1')
    assert lan.put('/api/users/' + admin['id'], json={'active': False}).status_code == 200


def test_writes_from_another_site_are_refused_but_the_server_hostname_works(server):
    client = signed_in('admin', 'admin-pass-1')
    body = {'name': 'x', 'settings': Settings().model_dump()}
    assert client.post('/api/presets', json=body, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert client.post('/api/presets', json=body, headers={'Origin': 'http://testserver'}).status_code == 200


def test_admin_bootstrap_runs_only_while_no_account_exists(server, monkeypatch):
    monkeypatch.setenv('TALKCUT_ADMIN_USERNAME', 'boss')
    monkeypatch.setenv('TALKCUT_ADMIN_PASSWORD', 'boss-pass-1')
    auth.bootstrap()
    assert not auth.find('boss')
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE kind='user'")
    auth.bootstrap()
    assert auth.find('boss')['role'] == 'admin' and auth.find('boss')['must_change_password']


def test_background_preparation_waits_behind_people_and_jumps_ahead_when_asked(monkeypatch):
    monkeypatch.setattr(pipeline, 'queues', {lane: pipeline.queue.PriorityQueue() for lane in pipeline.LANES})
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE kind='job'")
    early = pipeline.enqueue('focus', 'clip-a', {}, pipeline.BACKGROUND)
    late = pipeline.enqueue('focus', 'clip-b', {})
    render = pipeline.enqueue('render', 'clip-a', {})
    positions = pipeline.queue_positions(store.listing('job'))
    assert positions[late['id']] == 1 and positions[early['id']] == 2
    assert positions[render['id']] == 1  # its own lane: never behind framing work
    bumped = pipeline.enqueue('focus', 'clip-a', {})
    assert bumped['id'] == early['id'] and bumped['priority'] == pipeline.INTERACTIVE
    # The bumped job sits twice in the lane; it still runs exactly once.
    taken = []
    while not pipeline.queues['framing'].empty():
        _, _, id = pipeline.queues['framing'].get()
        if pipeline.claim(id):
            taken.append(id)
    assert sorted(taken) == sorted([early['id'], late['id']])


def test_records_made_by_a_job_belong_to_whoever_queued_it(monkeypatch):
    monkeypatch.setattr(pipeline, 'dispatch', lambda job, progress: store.create('export', {'title': 'x'}))
    job = store.create('job', {'kind': 'render', 'target': 't', 'payload': {}, 'status': 'running',
                               'created_by': {'id': 'u1', 'name': 'Lan'}})
    pipeline.run_job(job)
    assert store.get(job['id'], 'job')['status'] == 'completed'
    assert store.get(store.get(job['id'], 'job')['result']['id'], 'export')['created_by'] == {'id': 'u1', 'name': 'Lan'}
    assert store.actor.get() is None
