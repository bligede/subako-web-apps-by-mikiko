from datetime import timedelta
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketDisconnect
from conftest import login, scope, mutation_headers, ORIGIN
from subako.db import utcnow, aware, uid
from subako.models import Device, Reading, Session, TelemetryRaw, LedgerEntry, AlertAcknowledgement, User, SiteAccess
from subako.security import digest
from subako.seed import stable
from subako.schemas import Telemetry
from subako.services import ingest, verify_ledger
from subako.simulator import sample, tick
from subako.config import Settings


def test_auth_origin_session_rotation_and_logout(setup):
    client, database, app = setup
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "a@b.c", "password": "bad"}).status_code == 403
    session = login(client)
    cookie = client.cookies.get("subako_dev_session")
    assert cookie and len(cookie) > 40
    with database.session() as db:
        row = db.get(Session, digest(cookie))
        assert row and row.token_hash != cookie
    refresh = client.post("/api/v1/auth/refresh", headers=mutation_headers(session))
    assert refresh.status_code == 200
    assert refresh.json()["csrf_token"] != session["csrf_token"]
    assert client.cookies.get("subako_dev_session") != cookie
    assert client.get("/api/v1/auth/me", headers={"Cookie": f"subako_dev_session={cookie}"}).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=mutation_headers(refresh.json())).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("role,site_count,manage", [("viewer",1,False),("operator",2,False),("pekaseh",2,False),("admin",2,True)])
def test_role_and_site_scope(setup, role, site_count, manage):
    client, _, _ = setup
    session = login(client, role)
    assert len(session["sites"]) == site_count
    assert client.get("/api/v1/dashboard", params=scope()).status_code == 200
    assert client.get("/api/v1/admin/users", params=scope()).status_code == (200 if manage else 403)
    device = client.get("/api/v1/devices", params=scope()).json()["items"][0]
    changed = client.post(f"/api/v1/simulation/devices/{device['id']}/scenario", json={"scenario":"overcurrent"}, headers=mutation_headers(session))
    assert changed.status_code == (200 if manage else 403)
    assert client.get("/api/v1/dashboard", params=scope("kedewatan")).status_code == (404 if role=="viewer" else 200)
    if role == "viewer":
        other_device = stable(f"{stable('kedewatan')}:1")
        assert client.get(f"/api/v1/devices/{other_device}").status_code == 404
        params = {**scope(), "device_id":other_device, "from":(utcnow()-timedelta(days=1)).isoformat(), "to":utcnow().isoformat()}
        assert client.get("/api/v1/telemetry/history", params=params).status_code == 404


def test_csrf_ack_idempotency_and_audit_truth(setup):
    client, database, _ = setup
    session = login(client, "operator")
    alert = client.get("/api/v1/alerts", params=scope()).json()["items"][0]
    url = f"/api/v1/alerts/{alert['id']}/acknowledge"
    assert client.post(url, json={"note":"Petugas ditugaskan"}, headers={"Origin":ORIGIN,"Idempotency-Key":str(uuid4())}).status_code == 403
    headers = mutation_headers(session)
    bad_origin = {**headers,"Origin":"https://untrusted.example"}
    assert client.post(url, json={"note":"Petugas ditugaskan"}, headers=bad_origin).status_code == 403
    before = client.get(f"/api/v1/devices/{alert['device_id']}").json()["mode"]
    first = client.post(url, json={"note":"Petugas ditugaskan"}, headers=headers)
    second = client.post(url, json={"note":"Petugas ditugaskan"}, headers=headers)
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    assert client.post(url, json={"note":"Catatan payload berbeda"}, headers=headers).status_code == 409
    with database.session() as db:
        assert db.scalar(select(func.count()).select_from(AlertAcknowledgement)) == 1
    assert client.get(f"/api/v1/devices/{alert['device_id']}").json()["mode"] == before


def test_live_disabled_history_validation_and_no_secret_in_errors(setup):
    client, _, _ = setup
    login(client)
    assert client.get("/api/v1/dashboard",params={**scope(),"environment":"live"}).status_code == 422
    params={**scope(),"from":(utcnow()-timedelta(days=1)).isoformat(),"to":utcnow().isoformat(),"limit":5}
    first=client.get("/api/v1/telemetry/history",params=params)
    assert first.status_code==200 and len(first.json()["items"])==5
    second=client.get("/api/v1/telemetry/history",params={**params,"cursor":first.json()["next_cursor"]})
    assert second.status_code==200
    assert {r["id"] for r in first.json()["items"]}.isdisjoint(r["id"] for r in second.json()["items"])
    assert client.get("/api/v1/telemetry/history",params={**params,"cursor":"not-a-cursor"}).status_code==422
    assert client.get("/api/v1/telemetry/history",params={**params,"from":(utcnow()-timedelta(days=32)).isoformat()}).status_code==422
    response=client.post('/api/v1/auth/login',json={"email":"bad","password":"do-not-echo","secret":"do-not-echo"},headers={"Origin":ORIGIN})
    assert response.status_code==422 and "do-not-echo" not in response.text
    with pytest.raises(ValidationError):
        Settings(data_mode="live")
    with pytest.raises(ValidationError):
        Settings(app_env="production",cookie_secure=False)


def test_ingestion_duplicate_conflict_old_timestamp_and_quality(setup):
    _, database, _=setup
    with database.session.begin() as db:
        device=db.get(Device,stable(f"{stable('sembung')}:1"))
        payload=sample(device,100)
        first=ingest(db,payload)
        before=db.scalar(select(func.count()).select_from(Reading))
        assert ingest(db,payload)["duplicate"] is True
        assert db.scalar(select(func.count()).select_from(Reading))==before
        with pytest.raises(ValueError,match="SOURCE_EVENT_CONFLICT"):
            ingest(db,payload.model_copy(update={"battery_pct":2}))
        current=device.latest_observed_at
        ingest(db,sample(device,3,utcnow()-timedelta(hours=6)))
        assert aware(device.latest_observed_at)==aware(current)
        bad=payload.model_dump();bad.update(source_event_id=uid(),ts=utcnow(),quality={"level":"BAD","flow":"OK","encoder":"OK"})
        ingest(db,Telemetry(**bad))
        assert device.latest["water_level_m"] is None and device.latest["quality"]["level"]=="BAD"
        with pytest.raises(ValueError,match="FUTURE_TIMESTAMP"):
            ingest(db,sample(device,4,utcnow()+timedelta(minutes=10)))
        assert first["raw_id"]


@pytest.mark.parametrize("field,value",[("battery_pct",101),("gate_position_pct",-1),("flow_lps",float('nan')),("seq",65536),("quality",{"level":"INVALID","flow":"OK","encoder":"OK"})])
def test_invalid_telemetry_is_rejected(setup,field,value):
    _,database,_=setup
    with database.session() as db:
        device=db.get(Device,stable(f"{stable('sembung')}:1"))
        data=sample(device,1).model_dump();data[field]=value
        with pytest.raises(ValidationError):
            Telemetry(**data)


def test_sequence_wrap_does_not_drop_distinct_events(setup):
    _,database,_=setup
    with database.session.begin() as db:
        device=db.get(Device,stable(f"{stable('sembung')}:1"))
        raw_before=db.scalar(select(func.count()).select_from(TelemetryRaw))
        ingest(db,sample(device,65535))
        ingest(db,sample(device,65536))
        assert db.scalar(select(func.count()).select_from(TelemetryRaw))==raw_before+2


@pytest.mark.parametrize("scenario,mode",[("normal","AUTO"),("sensor_error","HOLD"),("device_offline",None),("low_battery","AUTO"),("overcurrent","FAULT"),("position_mismatch","FAULT"),("communication_failure",None)])
def test_seven_simulator_conditions(setup,scenario,mode):
    client,database,_=setup
    session=login(client,"admin")
    device_id=stable(f"{stable('sembung')}:1")
    before=client.get(f"/api/v1/devices/{device_id}").json()
    result=client.post(f"/api/v1/simulation/devices/{device_id}/scenario",json={"scenario":scenario},headers=mutation_headers(session))
    assert result.status_code==200
    tick(database,500)
    after=client.get(f"/api/v1/devices/{device_id}").json()
    assert after["scenario"]==scenario
    if mode:
        assert after["mode"]==mode and after["connectivity"]=="ONLINE"
    else:
        assert after["connectivity"]=="OFFLINE" and after["observed_at"]==before["observed_at"]
    if scenario=="sensor_error":
        assert after["water_level_m"] is None


def test_ledger_append_only_verification_and_tamper_detection(setup):
    client,database,_=setup
    login(client)
    verify=client.get("/api/v1/ledger/verify",params=scope()).json()
    assert verify["result"]=="VERIFIED" and verify["checked_count"]==4
    for sql in ["UPDATE ledger_entries SET current_hash='x'", "DELETE FROM ledger_entries", "DELETE FROM audit_events", "UPDATE telemetry_raw SET source='x'"]:
        with pytest.raises(IntegrityError):
            with database.session.begin() as db:
                db.execute(text(sql))
    # Explicit adversarial fixture: privileged attacker disables the trigger.
    with database.session.begin() as db:
        db.execute(text("DROP TRIGGER ledger_entries_no_update"))
        db.execute(text("UPDATE ledger_entries SET current_hash=:bad WHERE chain_index=1"),{"bad":"a"*64})
        assert verify_ledger(db,stable('sembung'))["result"]=="MISMATCH"


def test_websocket_origin_scope_and_logout_revocation(setup):
    client,database,_=setup
    session=login(client,"viewer")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/v1/sites/{stable('kedewatan')}?environment=simulation",headers={"Origin":ORIGIN}):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/v1/sites/{stable('sembung')}?environment=simulation",headers={"Origin":"https://untrusted.example"}):
            pass
    with client.websocket_connect(f"/ws/v1/sites/{stable('sembung')}?environment=simulation",headers={"Origin":ORIGIN}) as socket:
        event=socket.receive_json()
        assert event["site_id"]==stable('sembung') and event["type"]=="telemetry.updated"
        assert client.post('/api/v1/auth/logout',headers=mutation_headers(session)).status_code==204
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_login_rate_limit_and_disabled_account(setup):
    client,database,_=setup
    for _ in range(6):
        result=client.post('/api/v1/auth/login',json={"email":"nobody@example.invalid","password":"wrong"},headers={"Origin":ORIGIN})
        assert result.status_code==401
    assert client.post('/api/v1/auth/login',json={"email":"nobody@example.invalid","password":"wrong"},headers={"Origin":ORIGIN}).status_code==429
    login(client,"operator")
    with database.session.begin() as db:
        db.get(User,stable('operator')).active=False
    assert client.get('/api/v1/auth/me').status_code==401
