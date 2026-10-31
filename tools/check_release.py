"""Verify local release artifacts, a fresh backup/restore, and running dev HTTP."""
import ast
from datetime import datetime, timezone
import http.cookiejar
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from urllib.parse import unquote, urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'api'))
from subako.db import Database
from subako.models import Site
from subako.services import verify_ledger
from sqlalchemy import select


def run(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Release command failed: ' + ' '.join(str(x) for x in args[:3]))
    return result.stdout.strip()


def main():
    checks = {}
    for folder in ['apps/api/subako', 'apps/api/alembic', 'tools']:
        for path in (ROOT / folder).rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    checks['python_syntax'] = {'status': 'PASS'}
    checks['dependency_consistency'] = {'status': 'PASS', 'detail': run(sys.executable, '-m', 'pip', 'check')}

    compose = yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf-8'))
    assert set(compose['services']) == {'db', 'bootstrap', 'api', 'web'}
    assert 'ports' not in compose['services']['db']
    assert 'db_owner_password' not in compose['services']['api']['secrets']
    image_lock = json.loads((ROOT / 'infra/image-lock.json').read_text(encoding='utf-8'))
    configs = '\n'.join((ROOT / f).read_text(encoding='utf-8') for f in ['compose.yaml', 'apps/api/Dockerfile', 'apps/web/Dockerfile'])
    for image in image_lock['images']:
        assert f"{image['repository']}:{image['tag']}@{image['digest']}" in configs
    checks['compose_static'] = {'status': 'PASS', 'detail': 'YAML parsed; secret separation and four digest pins agree. Not docker compose config/build/up.'}

    report_path = ROOT / 'evidence/release-checks.json'
    broken = []
    for path in [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if re.match(r'^[a-z]+:', link) or link.startswith('#'):
                continue
            target = (path.parent / unquote(link.split('#')[0].strip('<>'))).resolve()
            if target != report_path and not target.exists():
                broken.append(str(path.relative_to(ROOT)) + ': ' + link)
    assert not broken, broken
    checks['documentation_links'] = {'status': 'PASS'}
    ignored = run('git', 'check-ignore', '.local/demo-credentials.json', '.local/subako-dev.db', '.venv/Scripts/python.exe', 'apps/web/node_modules/vite/package.json').splitlines()
    assert len(ignored) == 4
    checks['local_secret_exclusion'] = {'status': 'PASS', 'detail': 'Credential, database and installed dependency paths ignored by Git.'}

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / '.local/backups' / f'release-smoke-{stamp}.db'
    restored = ROOT / '.local' / f'restored-smoke-{stamp}.db'
    run(sys.executable, 'tools/backup_local.py', '--target', str(backup))
    run(sys.executable, 'tools/backup_local.py', '--restore', str(backup), '--target', str(restored))
    evidence = []
    for path in [backup, restored]:
        with sqlite3.connect(path) as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            counts = {name: db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                      for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()}
        database = Database('sqlite:///' + path.as_posix())
        with database.session() as db:
            chains = [verify_ledger(db, site.id) for site in db.scalars(select(Site).order_by(Site.id))]
            assert all(chain['result'] == 'VERIFIED' for chain in chains)
            evidence.append({'counts': counts, 'ledger_heads': [chain['head_hash'] for chain in chains]})
        database.engine.dispose()
    assert evidence[0] == evidence[1]
    rejected = subprocess.run([sys.executable, 'tools/backup_local.py', '--restore', str(backup), '--target', str(restored)], cwd=ROOT, capture_output=True, text=True)
    assert rejected.returncode != 0 and 'overwrite ditolak' in rejected.stderr
    checks['sqlite_backup_restore'] = {'status': 'PASS', 'table_counts': evidence[0]['counts'], 'sites_with_verified_ledger': len(evidence[0]['ledger_heads']), 'existing_target_overwrite': 'REJECTED'}

    origin = 'http://127.0.0.1:5173'
    credentials = json.loads((ROOT / '.local/demo-credentials.json').read_text(encoding='utf-8'))
    cookies = http.cookiejar.CookieJar()
    client = build_opener(HTTPCookieProcessor(cookies))
    with client.open(origin, timeout=10) as response:
        assert response.status == 200 and b'<html' in response.read()
    with client.open(origin + '/health/ready', timeout=10) as response:
        assert response.status == 200
    payload = json.dumps({'email': 'pekaseh@demo.subako.local', 'password': credentials['password']}).encode()
    request = Request(origin + '/api/v1/auth/login', data=payload, headers={'Content-Type': 'application/json', 'Origin': origin})
    with client.open(request, timeout=10) as response:
        session = json.load(response)
        assert 'HttpOnly' in response.headers['Set-Cookie']
    assert session['environment'] == 'simulation' and len(session['sites']) == 2
    params = urlencode({'site_id': session['sites'][0]['id'], 'environment': 'simulation'})
    with client.open(origin + '/api/v1/dashboard?' + params, timeout=10) as response:
        assert response.status == 200
    with client.open(Request(origin + '/api/v1/auth/logout', data=b'', headers={'Origin': origin, 'X-CSRF-Token': session['csrf_token']}), timeout=10) as response:
        assert response.status == 204
    checks['running_local_stack'] = {'status': 'PASS', 'url': origin, 'detail': 'Built shell, proxied readiness, actual demo login, dashboard read, logout. No credentials included.'}
    checks['docker_timescale_execution'] = {'status': 'NOT_RUN', 'detail': 'Compose plugin unavailable and Docker engine inactive on this host; revision 0003 and container stack unverified.'}

    report = {'release': '0.1.0-alpha.1', 'executed_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_WITH_DOCUMENTED_LIMITS', 'checks': checks}
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': {key: value['status'] for key, value in checks.items()}, 'report': str(report_path)}, indent=2))


if __name__ == '__main__':
    main()
