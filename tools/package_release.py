"""Package source, docs, built UI and test evidence; exclude local data/secrets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
SKIP_DIRS = {'.git', '.venv', '.local', 'node_modules', '__pycache__', '.pytest_cache', '.ruff_cache'}
SKIP_SUFFIXES = {'.pyc', '.db', '.db-wal', '.db-shm', '.log', '.jsonl', '.zip'}


def include(path):
    relative = path.relative_to(ROOT)
    return (not any(part in SKIP_DIRS or part.endswith('.egg-info') for part in relative.parts)
            and path.suffix.lower() not in SKIP_SUFFIXES
            and not path.name.startswith('e2e-failure')
            and (not path.name.startswith('.env') or path.name == '.env.example'))


def files(folder):
    for path in sorted(folder.iterdir()):
        if not include(path) or path.is_symlink():
            continue
        if path.is_dir():
            yield from files(path)
        elif path.is_file() and path.name != 'release-manifest.json':
            yield path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path,
                        default=ROOT.parent / 'output' / f'SUBAKO-Web-PWA-{VERSION}.zip')
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        raise SystemExit('Paket sudah ada; pilih nama output baru agar tidak menimpa artefak rilis.')
    if target.is_relative_to(ROOT):
        raise SystemExit('Simpan ZIP di luar folder source web-pwa.')
    selected = list(files(ROOT))
    manifest = {
        'release': VERSION, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'excludes': sorted(SKIP_DIRS | SKIP_SUFFIXES) + ['.env except .env.example', 'e2e-failure*'],
        'files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                   'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in selected:
            archive.write(path, 'web-pwa/' + path.relative_to(ROOT).as_posix())
        archive.writestr('web-pwa/release-manifest.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise SystemExit('ZIP integrity check failed.')
        for item in manifest['files']:
            if hashlib.sha256(archive.read('web-pwa/' + item['path'])).hexdigest() != item['sha256']:
                raise SystemExit('ZIP hash mismatch: ' + item['path'])
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(digest + '  ' + target.name + '\n', encoding='utf-8')
    print(json.dumps({'archive': str(target), 'files': len(selected) + 1,
                      'bytes': target.stat().st_size, 'sha256': digest, 'integrity': 'PASS'}, indent=2))


if __name__ == '__main__':
    main()
