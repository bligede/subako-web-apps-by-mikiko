"""Consistent SQLite backup / restore to a new file, never overwrite runtime DB."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--database',type=Path,default=ROOT/'.local'/'subako-dev.db')
parser.add_argument('--restore',type=Path)
parser.add_argument('--target',type=Path)
args=parser.parse_args()
source=(args.restore or args.database).resolve()
if not source.is_file():raise SystemExit('Database sumber tidak ditemukan.')
target=(args.target or ROOT/'.local'/'backups'/('subako-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.db')).resolve()
if args.restore and not args.target:raise SystemExit('Restore memerlukan --target dengan nama database baru.')
if target.exists() or target==source:raise SystemExit('Target harus berupa file baru; overwrite ditolak.')
target.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect('file:'+source.as_posix()+'?mode=ro',uri=True) as src,sqlite3.connect(target) as dst:
    src.backup(dst)
    result=dst.execute('PRAGMA integrity_check').fetchone()[0]
    if result!='ok':raise SystemExit('Integrity check gagal: '+result)
print('Restore' if args.restore else 'Backup','selesai:',target,'| integrity_check=ok')
