"""Delete an old source and everything derived from it, to free server disk.

Removed: the source folder (original, preview copy, transcript, thumbnails),
its clips and their edits, the job history of the source and its clips, and
the framing caches of those clips. Exported videos are kept unless asked for:
they are self-contained and are what people came for.
"""
import shutil
from pathlib import Path

from . import config, store

ACTIVE = ('queued', 'running')


class SourceBusy(ValueError):
    pass


def related(source):
    clips = [c for c in store.listing('clip') if c.get('source_id') == source['id']]
    targets = {source['id'], *(c['id'] for c in clips)}
    jobs = [j for j in store.listing('job') if j.get('target') in targets]
    exports = [e for e in store.listing('export') if e.get('source_id') == source['id']]
    return clips, jobs, exports


def size(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
    return 0


def source_folder(source):
    folder = (config.DATA / 'sources' / source['id']).resolve()
    return folder if folder.parent == (config.DATA / 'sources').resolve() else None


def export_folder(item):
    """The render job folder of an export (final.mp4 plus its intermediates)."""
    renders = (config.DATA / 'renders').resolve()
    target = (config.DATA / item['path']).resolve()
    return target.parent if target.parent.parent == renders else None


def cache_folders(source, clips):
    """Framing caches are keyed by the source file and clip bounds, so they
    must be located while the source file still exists. Caches of older
    analysis versions or earlier trims are not traceable and stay behind."""
    from . import director, focus, stacked_view
    path = config.DATA / source['path'] if source.get('path') else None
    if not path or not path.is_file():
        return set()
    found = set()
    for clip in clips:
        settings = clip.get('settings') or {}
        makers = [lambda: director.cache_dir(path, clip), lambda: focus.cache_dir(path, clip),
                  lambda: focus.cache_dir(path, {**clip, 'settings': {}})]
        top, bottom = settings.get('tracking_subject'), settings.get('tracking_subject_2')
        if top and bottom:
            makers.append(lambda: stacked_view.cache_dir(path, clip, top, bottom))
        for make in makers:
            try:
                folder = make()
            except Exception:
                continue
            if folder.is_dir():
                found.add(folder)
    return found


def summary(source):
    clips, jobs, exports = related(source)
    folder = source_folder(source)
    return {
        'clips': len(clips),
        'exports': len(exports),
        'busy': sum(j['status'] in ACTIVE for j in jobs),
        'source_bytes': size(folder) if folder else 0,
        'cache_bytes': sum(size(f) for f in cache_folders(source, clips)),
        'export_bytes': sum(size(f) for f in filter(None, map(export_folder, exports))),
    }


def remove(source, delete_exports=False, may_delete=lambda record: True):
    """may_delete decides per export: someone else's exported video is kept."""
    clips, jobs, exports = related(source)
    busy = [j for j in jobs if j['status'] in ACTIVE]
    if busy:
        raise SourceBusy(f'Nguồn này đang có {len(busy)} tác vụ chạy hoặc đang chờ. Đợi xong rồi xóa.')
    doomed = [e for e in exports if may_delete(e)] if delete_exports else []
    folders = [source_folder(source), *cache_folders(source, clips), *map(export_folder, doomed)]
    folders = [f for f in folders if f]
    freed = sum(size(f) for f in folders)
    records = [(source['id'], 'source'), *((c['id'], 'clip') for c in clips), *((j['id'], 'job') for j in jobs),
               *((e['id'], 'export') for e in doomed)]
    # Records go in one transaction first, so the library never shows a half-deleted source.
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.executemany('DELETE FROM records WHERE id=? AND kind=?', records)
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=True)
    return {'deleted': True, 'freed_bytes': freed, 'clips': len(clips),
            'exports_deleted': len(doomed), 'exports_kept': len(exports) - len(doomed)}
