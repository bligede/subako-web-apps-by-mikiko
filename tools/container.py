"""Compose entry point: bootstrap holds owner key; API holds runtime keys only."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
API=ROOT/'apps'/'api'
sys.path.insert(0,str(API))
bootstrap=len(sys.argv)>1 and sys.argv[1]=='bootstrap'
keys=['db_owner_password','db_api_password','db_ingest_password','demo_password'] if bootstrap else ['db_api_password','db_ingest_password']
loaded={name:(Path('/run/secrets')/name).read_text(encoding='utf-8').strip() for name in keys}
if hasattr(os,'geteuid') and os.geteuid()==0:
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)


def secret(name):
    value=loaded[name]
    if len(value)<14:raise RuntimeError(f'Secret {name} belum dikonfigurasi.')
    return value


def url(role,key):
    from sqlalchemy.engine import URL
    return URL.create('postgresql+psycopg',username=role,password=secret(key),host='db',port=5432,database='subako').render_as_string(hide_password=False)


if bootstrap:
    from alembic import command
    from alembic.config import Config
    import psycopg
    from psycopg import sql
    owner=url('subako_owner','db_owner_password')
    os.environ['SUBAKO_DATABASE_URL']=owner
    config=Config(str(API/'alembic.ini'));config.attributes['database_url']=owner
    command.upgrade(config,'head')
    with psycopg.connect(owner.replace('postgresql+psycopg:','postgresql:'),autocommit=True) as connection:
        for role,key in [('subako_api','db_api_password'),('subako_ingest','db_ingest_password')]:
            connection.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role),sql.Literal(secret(key))))
    if os.environ.get('SUBAKO_SEED_DEMO','false').lower()=='true':
        from subako.config import Settings
        from subako.db import Database
        from subako.seed import seed
        seed(Database(owner),secret('demo_password'),Settings())
    print('Schema, TimescaleDB, runtime roles and optional simulation seed initialized.')
else:
    os.environ['SUBAKO_DATABASE_URL']=url('subako_api','db_api_password')
    os.environ['SUBAKO_SIMULATOR_DATABASE_URL']=url('subako_ingest','db_ingest_password')
    import uvicorn
    uvicorn.run('subako.main:app',host='0.0.0.0',port=8000,workers=1,access_log=False)
