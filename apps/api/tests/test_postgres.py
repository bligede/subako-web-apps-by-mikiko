"""Real embedded PostgreSQL: migrations 0001/0002, runtime roles and RLS.

TimescaleDB is not included in pgserver. Revision 0003 requires the Compose
TimescaleDB image and is explicitly outside this compatibility test.
"""
import secrets
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, text, func
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from fastapi.testclient import TestClient
from conftest import migrate, PASSWORD, login, scope, mutation_headers
from subako.db import Database
from subako.config import Settings
from subako.seed import seed, stable
from subako.models import Device, LedgerEntry, User
from subako.services import append_ledger, verify_ledger
from subako.security import set_principal_context
from subako.simulator import tick
from subako.main import create_app


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    pgserver=pytest.importorskip('pgserver')
    import psycopg
    from psycopg import sql
    server=pgserver.get_server(str(tmp_path_factory.mktemp('postgres')),cleanup_mode='stop')
    uri=server.get_uri()
    owner_url=make_url(uri).set(drivername='postgresql+psycopg')
    rendered=owner_url.render_as_string(hide_password=False)
    migrate(rendered,'0002')
    owner=Database(rendered)
    cfg=Settings(app_env='testing',database_url=rendered,simulator_enabled=False)
    seed(owner,PASSWORD,cfg)
    api_password=secrets.token_urlsafe(24);ingest_password=secrets.token_urlsafe(24)
    with psycopg.connect(uri,autocommit=True) as connection:
        for role,password in [('subako_api',api_password),('subako_ingest',ingest_password)]:
            connection.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
    api_url=owner_url.set(username='subako_api',password=api_password).render_as_string(hide_password=False)
    ingest_url=owner_url.set(username='subako_ingest',password=ingest_password).render_as_string(hide_password=False)
    api_db,ingest_db=Database(api_url),Database(ingest_url)
    yield owner,api_db,ingest_db
    api_db.engine.dispose();ingest_db.engine.dispose();owner.engine.dispose()


def test_real_postgres_rls_roles_and_default_deny(pg):
    _,api_db,ingest_db=pg
    with api_db.session() as db:
        assert db.scalar(text('SELECT current_user'))=='subako_api'
        assert list(db.scalars(select(Device)))==[]
        set_principal_context(db,stable('viewer'))
        devices=list(db.scalars(select(Device)))
        assert len(devices)==4 and all(d.site_id==stable('sembung') for d in devices)
        assert list(db.scalars(select(Device).where(Device.site_id==stable('kedewatan'))))==[]
    with api_db.session() as db:
        assert list(db.scalars(select(Device)))==[]  # transaction-local context reset
    for database,statement in [(api_db,"INSERT INTO ledger_entries DEFAULT VALUES"),(ingest_db,"SELECT * FROM users"),(ingest_db,"DELETE FROM ledger_entries")]:
        with pytest.raises(DBAPIError):
            with database.session.begin() as db:
                db.execute(text(statement))


def test_api_and_simulator_under_distinct_postgres_roles(pg):
    _,api_db,ingest_db=pg
    cfg=Settings(app_env='testing',database_url=api_db.engine.url.render_as_string(hide_password=False),simulator_enabled=False)
    with TestClient(create_app(cfg,api_db)) as client:
        session=login(client,'viewer')
        assert client.get('/api/v1/dashboard',params=scope()).status_code==200
        assert client.get('/api/v1/dashboard',params=scope('kedewatan')).status_code==404
        login(client,'admin')
        devices=client.get('/api/v1/devices',params=scope()).json()['items']
        admin=client.get('/api/v1/auth/me').json()
        scenario=client.post(f"/api/v1/simulation/devices/{devices[0]['id']}/scenario",json={'scenario':'normal'},headers=mutation_headers(admin))
        assert scenario.status_code==200
        alert=client.get('/api/v1/alerts',params=scope()).json()['items'][0]
        acknowledged=client.post(f"/api/v1/alerts/{alert['id']}/acknowledge",json={'note':'Uji acknowledgement pada runtime role PostgreSQL.'},headers=mutation_headers(admin))
        assert acknowledged.status_code==200
        with ingest_db.session() as db:
            assert db.scalar(text('SELECT current_user'))=='subako_ingest'
        assert stable('sembung') in tick(ingest_db,999)
        verify=client.get('/api/v1/ledger/verify',params=scope())
        assert verify.status_code==200 and verify.json()['result']=='VERIFIED'


def test_postgres_append_only_and_concurrent_chain(pg):
    owner,_,ingest_db=pg
    for statement in ["DELETE FROM ledger_entries", "UPDATE audit_events SET outcome='FAILED'", "TRUNCATE telemetry_raw CASCADE"]:
        with pytest.raises(DBAPIError,match='append-only'):
            with owner.session.begin() as db:
                db.execute(text(statement))
    def append(index):
        with ingest_db.session.begin() as db:
            append_ledger(db,stable('sembung'),{'kind':'CONCURRENT_TEST','index':index})
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(append,range(8)))
    with owner.session() as db:
        assert verify_ledger(db,stable('sembung'))['result']=='VERIFIED'
        count=db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.site_id==stable('sembung')))
        distinct=db.scalar(select(func.count(func.distinct(LedgerEntry.chain_index))).where(LedgerEntry.site_id==stable('sembung')))
        assert count==distinct
