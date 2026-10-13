"""Accounts issued by an administrator, with server-side cookie sessions.

Off unless TALKCUT_AUTH is on (the personal desktop install stays as before).
Passwords are stored as salted scrypt hashes; the session cookie carries a
random token whose SHA-256 is the only thing kept in the database.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from . import config, store

COOKIE = 'talkcut_session'
SESSION_SECONDS = 14 * 24 * 3600
ROLES = ('admin', 'editor')


class AuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _b64(raw):
    return base64.b64encode(raw).decode()


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f'scrypt$16384$8$1${_b64(salt)}${_b64(digest)}'


def verify_password(password, stored):
    try:
        _, n, r, p, salt, digest = stored.split('$')
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# Compared against for unknown usernames so both paths cost the same time.
_DUMMY = hash_password(secrets.token_hex(8))


def init():
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id)')


def public(user):
    return {k: user.get(k) for k in ('id', 'username', 'display_name', 'role', 'active', 'must_change_password', 'created')}


def owner(user):
    """What a record keeps about its creator: enough to show a name."""
    return user and {'id': user['id'], 'name': user['display_name']}


def users():
    return store.listing('user')


def find(username):
    key = username.strip().lower()
    return next((u for u in users() if u['username'] == key), None)


def _check_password(password):
    if not isinstance(password, str) or len(password) < 8:
        raise AuthError('Mật khẩu cần ít nhất 8 ký tự.')
    if len(password) > 200:
        raise AuthError('Mật khẩu quá dài.')


def create_user(username, display_name, password, role='editor', must_change=True):
    username = (username or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9._-]{3,40}', username):
        raise AuthError('Tên đăng nhập dài 3–40 ký tự, chỉ gồm chữ thường không dấu, số và . _ -')
    if role not in ROLES:
        raise AuthError('Vai trò không hợp lệ.')
    _check_password(password)
    if find(username):
        raise AuthError('Tên đăng nhập đã tồn tại.')
    display_name = (display_name or '').strip()[:80] or username
    return store.create('user', {'username': username, 'display_name': display_name, 'role': role, 'active': True,
                                 'password_hash': hash_password(password), 'must_change_password': must_change})


def update_user(id, actor, display_name=None, role=None, active=None, password=None):
    user = store.get(id, 'user')
    changes = {}
    if display_name is not None:
        changes['display_name'] = display_name.strip()[:80] or user['username']
    if role is not None:
        if role not in ROLES:
            raise AuthError('Vai trò không hợp lệ.')
        changes['role'] = role
    if active is not None:
        changes['active'] = bool(active)
    if password is not None:
        _check_password(password)
        changes.update(password_hash=hash_password(password), must_change_password=True)
    after = {**user, **changes}
    if user['role'] == 'admin' and user['active'] and not (after['role'] == 'admin' and after['active']):
        if id == actor['id']:
            raise AuthError('Không thể tự gỡ quyền quản trị hoặc khóa tài khoản của chính mình.')
        if not any(u['id'] != id and u['role'] == 'admin' and u['active'] for u in users()):
            raise AuthError('Cần giữ ít nhất một quản trị viên đang hoạt động.')
    user = store.update(id, **changes)
    if active is False or password is not None:
        end_sessions(id)
    return user


def change_password(user, current_password, new_password):
    if not verify_password(current_password or '', user['password_hash']):
        raise AuthError('Mật khẩu hiện tại chưa đúng.')
    _check_password(new_password)
    if current_password == new_password:
        raise AuthError('Hãy chọn mật khẩu mới khác mật khẩu hiện tại.')
    return store.update(user['id'], password_hash=hash_password(new_password), must_change_password=False)


# Repeated wrong passwords for one name from one address wait 15 minutes.
_failures, _failures_lock = {}, threading.Lock()
MAX_FAILURES, WINDOW = 5, 15 * 60


def login(username, password, address):
    key = ((username or '').strip().lower(), address or '')
    now = time.time()
    with _failures_lock:
        recent = [t for t in _failures.get(key, []) if now - t < WINDOW]
        _failures[key] = recent
        if len(recent) >= MAX_FAILURES:
            raise AuthError('Đăng nhập sai quá nhiều lần. Hãy thử lại sau 15 phút.', 429)
    user = find(key[0])
    valid = verify_password(password or '', user['password_hash'] if user else _DUMMY)
    if not user or not valid or not user.get('active'):
        with _failures_lock:
            _failures.setdefault(key, []).append(now)
        raise AuthError('Tên đăng nhập hoặc mật khẩu chưa đúng.' if not user or not valid else 'Tài khoản đã bị khóa. Hãy liên hệ quản trị viên.', 401)
    with _failures_lock:
        _failures.pop(key, None)
    token = secrets.token_urlsafe(32)
    with store.connect() as db:
        db.execute('DELETE FROM sessions WHERE expires < ?', (now,))
        db.execute('INSERT INTO sessions VALUES (?, ?, ?, ?)', (_digest(token), user['id'], now, now + SESSION_SECONDS))
    return user, token


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def session_user(token):
    if not token:
        return None
    with store.connect() as db:
        row = db.execute('SELECT user_id, expires FROM sessions WHERE token_hash=?', (_digest(token),)).fetchone()
    if not row or row['expires'] < time.time():
        return None
    try:
        user = store.get(row['user_id'], 'user')
    except KeyError:
        return None
    return user if user.get('active') else None


def logout(token):
    if token:
        with store.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (_digest(token),))


def end_sessions(user_id):
    with store.connect() as db:
        db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))


def may_manage(user, record):
    """Admins manage everything; editors their own records and pre-login ones."""
    if not config.AUTH_ENABLED or not user:
        return True
    created_by = record.get('created_by')
    return user['role'] == 'admin' or not created_by or created_by.get('id') == user['id']


def bootstrap():
    """First administrator from TALKCUT_ADMIN_USERNAME/PASSWORD, only while no user exists."""
    init()
    username, password = os.getenv('TALKCUT_ADMIN_USERNAME', ''), os.getenv('TALKCUT_ADMIN_PASSWORD', '')
    if config.AUTH_ENABLED and username and password and not users():
        create_user(username, 'Quản trị viên', password, 'admin', must_change=True)


def main(argv=None):
    """docker compose exec studio python -m backend.auth create-admin <username>"""
    import argparse
    import getpass
    parser = argparse.ArgumentParser(description='Quản lý tài khoản TalkCut')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create-admin', help='Tạo tài khoản quản trị viên')
    create.add_argument('username')
    reset = sub.add_parser('reset-password', help='Đặt lại mật khẩu (người dùng phải đổi khi đăng nhập)')
    reset.add_argument('username')
    sub.add_parser('list', help='Liệt kê tài khoản')
    args = parser.parse_args(argv)
    init()
    if args.command == 'list':
        for u in users():
            print(u['username'], u['role'], 'active' if u['active'] else 'locked', u['display_name'])
        return
    password = os.getenv('TALKCUT_NEW_PASSWORD') or getpass.getpass('Mật khẩu mới: ')
    try:
        if args.command == 'create-admin':
            create_user(args.username, 'Quản trị viên', password, 'admin', must_change=False)
            print('Đã tạo quản trị viên', args.username)
        else:
            user = find(args.username)
            if not user:
                raise AuthError('Không có tài khoản này.')
            store.update(user['id'], password_hash=hash_password(password), must_change_password=True, active=True)
            end_sessions(user['id'])
            print('Đã đặt lại mật khẩu cho', user['username'])
    except AuthError as error:
        raise SystemExit(str(error))


if __name__ == '__main__':
    main()
