#!/usr/bin/env python3
"""Local version checkpoints and non-destructive application rollback."""
import argparse,json,os,re,subprocess,sys,datetime
from pathlib import Path
# Windows terminals default to a non-UTF-8 codepage that cannot print the
# Vietnamese status messages below; force UTF-8 so the checkpoint work above
# (already done by this point) is not hidden behind a crash on the last print.
try:sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
except Exception:pass
ROOT=Path(__file__).resolve().parents[1]
RELEASES=ROOT/'.releases'

def run(*args,env=None):
    return subprocess.check_output(args,cwd=ROOT,text=True,env=env).strip()

def idle():
    code="from backend import store; assert not any(j['status'] in ('running','queued') for j in store.listing('job')), 'Đợi tác vụ hiện tại hoàn tất trước khi đổi phiên bản.'"
    run('docker','compose','exec','-T','studio','python','-c',code)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['list','checkpoint','rollback','development']);parser.add_argument('version',nargs='?');parser.add_argument('--accepted',action='store_true',help='Chỉ dùng khi người dùng đã xác nhận bản này ổn định.')
    args=parser.parse_args();RELEASES.mkdir(exist_ok=True)
    if args.action=='list':
        for p in sorted(RELEASES.glob('*.json')):
            m=json.loads(p.read_text());print(m['version'],m['status'],m['commit'][:8],m['image'])
        return
    idle()
    if args.action=='development':
        env={**os.environ,'TALKCUT_IMAGE':'talkcut-studio-studio:latest','TALKCUT_FACE_IMAGE':'talkcut-face-engine:latest'}
        run('docker','compose','up','-d','--build','studio','face-engine',env=env)
        (ROOT/'.active-image').unlink(missing_ok=True);print('Đã chuyển sang bản phát triển.');return
    version=args.version or ''
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?',version):parser.error('Dùng version như v0.4.0-rc.1 hoặc v0.4.0.')
    path=RELEASES/(version+'.json')
    if args.action=='checkpoint':
        if path.exists():parser.error('Version đã tồn tại; checkpoint không bị ghi đè.')
        if run('git','status','--porcelain'):parser.error('Commit thay đổi trước khi chốt version.')
        commit=run('git','rev-parse','HEAD');image='talkcut-studio:'+version;face_image='talkcut-face-engine:'+version
        # Both local services are versioned together.  A tracking checkpoint
        # must never silently load a newer face engine during rollback.
        env={**os.environ,'TALKCUT_IMAGE':image,'TALKCUT_FACE_IMAGE':face_image}
        run('docker','compose','build','studio','face-engine',env=env)
        backup='/data/checkpoints/'+version+'.sqlite'
        code=f"import sqlite3; from pathlib import Path; from backend import config; p=Path({backup!r}); p.parent.mkdir(exist_ok=True); a=sqlite3.connect(config.DATA/'studio.sqlite'); b=sqlite3.connect(p); a.backup(b); b.close(); a.close()"
        run('docker','compose','exec','-T','studio','python','-c',code)
        run('git','tag','-a',version,'-m',('Stable accepted version ' if args.accepted else 'Review candidate ')+version)
        status='stable' if args.accepted else 'candidate'
        path.write_text(json.dumps({'version':version,'status':status,'commit':commit,'image':image,'face_image':face_image,'database_snapshot':backup,'created':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
        print(f'Đã lưu {version} ({status}). Git tag cần push khi công bố.');return
    if not path.exists():parser.error('Chưa có checkpoint local cho version này.')
    m=json.loads(path.read_text());image=m['image'];face_image=m.get('face_image','talkcut-face-engine:latest')
    run('docker','image','inspect',image,'--format','{{.Id}}')
    run('docker','image','inspect',face_image,'--format','{{.Id}}')
    env={**os.environ,'TALKCUT_IMAGE':image,'TALKCUT_FACE_IMAGE':face_image}
    run('docker','compose','up','-d','--no-build','studio','face-engine',env=env)
    (ROOT/'.active-image').write_text(image+'\n')
    print(f'Đã chạy {version}. Giữ nguyên database/media hiện tại; không ghi đè các chỉnh sửa mới.')

if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as e:sys.exit(e.returncode)
