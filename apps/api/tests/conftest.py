from pathlib import Path
import sys
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
from subako.config import Settings
from subako.db import Database
from subako.seed import seed, stable
from subako.main import create_app

PASSWORD = "Fixture-Only-Password-2026!"
ORIGIN = "http://127.0.0.1:5173"


def migrate(url, revision="head"):
    config = Config(str(API / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, revision)


@pytest.fixture
def setup(tmp_path):
    url = "sqlite:///" + str(tmp_path / "test.db").replace("\\", "/")
    migrate(url)
    cfg = Settings(app_env="testing", database_url=url, simulator_enabled=False)
    db = Database(url)
    seed(db, PASSWORD, cfg)
    app = create_app(cfg, db)
    with TestClient(app) as client:
        yield client, db, app
    db.engine.dispose()


def login(client, role="pekaseh"):
    response = client.post("/api/v1/auth/login", json={"email": f"{role}@demo.subako.local", "password": PASSWORD}, headers={"Origin": ORIGIN})
    assert response.status_code == 200, response.text
    return response.json()


def scope(site="sembung"):
    return {"site_id": stable(site), "environment": "simulation"}


def mutation_headers(session, key=None):
    from uuid import uuid4
    return {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"], "Idempotency-Key": str(key or uuid4())}
