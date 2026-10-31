"""Start an isolated local SIMULATION environment; no Docker/hardware needed."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
API=ROOT/'apps'/'api'
sys.path.insert(0,str(API))


def prepare():
    local=ROOT/'.local';local.mkdir(exist_ok=True)
    os.environ.setdefault('SUBAKO_DATABASE_URL','sqlite:///'+(local/'subako-dev.db').as_posix())
    os.environ.setdefault('SUBAKO_APP_ENV','development')
    os.environ.setdefault('SUBAKO_ALLOWED_ORIGINS',json.dumps(['http://127.0.0.1:5173','http://localhost:5173']))
    credentials=local/'demo-credentials.json'
    if credentials.exists():
        password=json.loads(credentials.read_text(encoding='utf-8'))['password']
    else:
        password=secrets.token_urlsafe(20)
        credentials.write_text(json.dumps({'environment':'LOCAL SIMULATION ONLY','accounts':['viewer@demo.subako.local','operator@demo.subako.local','pekaseh@demo.subako.local','admin@demo.subako.local'],'password':password},indent=2),encoding='utf-8')
    from alembic import command
    from alembic.config import Config
    from subako.config import Settings
    from subako.db import Database
    from subako.seed import seed
    cfg=Settings()
    migration=Config(str(API/'alembic.ini'));migration.attributes['database_url']=cfg.database_url
    command.upgrade(migration,'head')
    seed(Database(cfg.database_url),password,cfg)
    print('Local SIMULATION database ready. Credentials file:',credentials,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--built',action='store_true');args=parser.parse_args()
    if not args.prepare_only:
        for port in (8000,5173):
            with socket.socket() as probe:
                try:probe.bind(('127.0.0.1',port))
                except OSError:raise SystemExit(f'Port {port} sedang digunakan; hentikan instance sebelumnya.')
    prepare()
    if args.prepare_only:return
    web=ROOT/'apps'/'web';vite=web/'node_modules'/'vite'/'bin'/'vite.js'
    if not vite.exists():raise SystemExit('Install frontend dependencies first: npm ci in apps/web.')
    if args.built and not (web/'dist'/'index.html').exists():raise SystemExit('Build frontend first: npm run build in apps/web.')
    processes=[]
    def stop(*_):
        for process in processes:
            if process.poll() is None:process.terminate()
        for process in processes:
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill()
        raise SystemExit(0)
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    try:
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','subako.main:app','--host','127.0.0.1','--port','8000','--no-access-log'],cwd=API,env=os.environ.copy()))
        processes.append(subprocess.Popen(['node',str(vite),*(['preview'] if args.built else []),'--host','127.0.0.1','--port','5173','--strictPort'],cwd=web,env=os.environ.copy()))
        print('SUBAKO: http://127.0.0.1:5173 | Swagger: http://127.0.0.1:8000/docs',flush=True)
        while all(p.poll() is None for p in processes):time.sleep(1)
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()


if __name__=='__main__':main()
