import json
import sqlite3
import time
import uuid
from .config import DATA


def connect():
    db = sqlite3.connect(DATA / 'studio.sqlite', timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.row_factory = sqlite3.Row
    return db


def init():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS records_kind_created ON records(kind, created DESC)')


def create(kind, payload):
    item = {'id': uuid.uuid4().hex, 'created': time.time(), **payload}
    with connect() as db:
        db.execute('INSERT INTO records VALUES (?, ?, ?, ?)', (item['id'], kind, item['created'], json.dumps(item, ensure_ascii=False)))
    return item


def get(id, kind=None):
    with connect() as db:
        row = db.execute('SELECT kind,payload FROM records WHERE id=?', (id,)).fetchone()
    if not row or (kind and kind != row['kind']):
        raise KeyError('Không tìm thấy dữ liệu.')
    return json.loads(row['payload'])


def update(id, **changes):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM records WHERE id=?', (id,)).fetchone()
        if not row:
            raise KeyError('Không tìm thấy dữ liệu.')
        item = {**json.loads(row['payload']), **changes}
        db.execute('UPDATE records SET payload=? WHERE id=?', (json.dumps(item, ensure_ascii=False), id))
    return item


def listing(kind):
    with connect() as db:
        rows = db.execute('SELECT payload FROM records WHERE kind=? ORDER BY created DESC', (kind,)).fetchall()
    return [json.loads(row['payload']) for row in rows]


init()
