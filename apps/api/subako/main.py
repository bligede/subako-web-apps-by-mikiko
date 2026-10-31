import asyncio
import base64
import csv
import io
import json
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, Request, Response, HTTPException, Query, Header, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, or_, and_, inspect
from sqlalchemy.exc import IntegrityError
from . import __version__
from .config import Settings
from .db import Database, utcnow, uid, aware
from .models import User, Session, Site, SiteAccess, UserRole, Device, Reading, Alert, AlertAcknowledgement, LedgerEntry, AuditEvent, LoginAttempt, MutationKey
from .schemas import Login, Acknowledge, ScenarioChange
from .security import principal, principal_from_token, authorize, permissions, new_session, csrf_for, digest, verify_password, dummy_hash, audit, set_principal_context
from .services import dashboard, device_view, verify_ledger, timestamp, canonical
from .simulator import run as simulate

log = logging.getLogger("subako.api")


def create_app(settings=None, database=None):
    cfg = settings or Settings()
    database = database or Database(cfg.database_url)

    @asynccontextmanager
    async def lifespan(app):
        if "alembic_version" not in inspect(database.engine).get_table_names():
            raise RuntimeError("Database belum dimigrasi. Jalankan alembic upgrade head.")
        task = asyncio.create_task(simulate(app)) if cfg.simulator_enabled else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="SUBAKO Foundation API", version=__version__, description="Phase 1 + dashboard simulasi. LIVE dan command aktuasi belum diaktifkan. Semua data berlabel SIMULATION.", lifespan=lifespan)
    app.state.settings, app.state.db, app.state.versions = cfg, database, {}
    app.state.simdb = Database(cfg.simulator_database_url) if cfg.simulator_database_url else database

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = uid()
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and request.headers.get("origin") not in cfg.allowed_origins:
            response = JSONResponse({"code": "ORIGIN_DENIED", "message": "Origin permintaan tidak diizinkan.", "request_id": request.state.request_id}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "REQUEST_FAILED", "message": str(exc.detail)}
        return JSONResponse({**detail, "request_id": getattr(request.state, "request_id", uid())}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"code": "VALIDATION_ERROR", "message": "Format permintaan tidak valid.", "request_id": getattr(request.state, "request_id", uid()), "details": [{"field": ".".join(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()]}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse({"code": "TRANSACTION_CONFLICT", "message": "Transaksi berbenturan. Muat ulang status sebelum tindakan baru.", "request_id": request.state.request_id}, status_code=409)

    def session_view(db, identity):
        set_principal_context(db, identity.user.id)
        grants = []
        for site in db.scalars(select(Site).join(SiteAccess).where(SiteAccess.user_id == identity.user.id).order_by(Site.name)):
            roles = list(db.scalars(select(UserRole.role_code).where(UserRole.user_id == identity.user.id, UserRole.site_id == site.id)))
            grants.append({"id": site.id, "name": site.name, "location": site.location, "environment": site.environment, "roles": roles, "permissions": sorted(permissions(db, identity.user.id, site.id))})
        return {"user": {"id": identity.user.id, "email": identity.user.email, "display_name": identity.user.display_name}, "sites": grants, "csrf_token": csrf_for(identity.token), "expires_at": timestamp(identity.session.expires_at), "environment": "simulation"}

    def set_cookie(response, token):
        response.set_cookie(cfg.cookie_name, token, httponly=True, secure=cfg.cookie_secure, samesite="lax", path="/", max_age=cfg.session_absolute_seconds)

    def scope(db, request, site_id, environment, permission="dashboard.read", mutate=False):
        identity = principal(request, db, mutate=mutate)
        authorize(db, identity, str(site_id), permission)
        return identity

    def require_device(db, request, device_id, permission="device.read", mutate=False):
        identity = principal(request, db, mutate=mutate)
        device = db.get(Device, str(device_id))
        if not device:
            raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Perangkat tidak ditemukan."})
        authorize(db, identity, device.site_id, permission)
        return identity, device

    def idempotency(db, identity, key, action, resource, payload):
        fingerprint = digest(canonical({"action": action, "resource": resource, "payload": payload}))
        previous = db.get(MutationKey, (identity.user.id, str(key)))
        if previous and previous.payload_hash != fingerprint:
            raise HTTPException(409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": "Idempotency-Key telah digunakan untuk payload berbeda."})
        return previous, fingerprint

    @app.get("/health/live", tags=["Health"])
    def live():
        return {"status": "UP", "version": __version__, "environment": "SIMULATION", "live_enabled": False}

    @app.get("/health/ready", tags=["Health"])
    def ready():
        with database.session() as db:
            db.execute(select(func.count()).select_from(Site))
        return {"status": "READY", "database": database.engine.dialect.name, "timescale_requested": cfg.timescale_enabled, "live_enabled": False}

    @app.post("/api/v1/auth/login", tags=["Authentication"])
    def login(body: Login, request: Request, response: Response):
        with database.session() as db:
            bucket = digest(f"{request.client.host}:{body.email}")
            recent = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.bucket == bucket, LoginAttempt.attempted_at > utcnow()-timedelta(seconds=60)))
            ip_bucket = digest(f"ip:{request.client.host}")
            ip_recent = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.bucket == ip_bucket, LoginAttempt.attempted_at > utcnow()-timedelta(seconds=60)))
            if recent >= 6 or ip_recent >= 30:
                raise HTTPException(429, detail={"code": "LOGIN_RATE_LIMIT", "message": "Terlalu banyak percobaan. Coba lagi setelah satu menit."}, headers={"Retry-After": "60"})
            db.add_all([LoginAttempt(bucket=bucket), LoginAttempt(bucket=ip_bucket)])
            user = db.scalar(select(User).where(User.email == body.email))
            verified = verify_password(user.password_hash if user else dummy_hash, body.password)
            if not user or not verified or not user.active:
                audit(db, None, "auth.login", outcome="DENIED")
                db.commit()
                raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Email atau kata sandi tidak sesuai."})
            # Revoke the existing browser session before replacing its cookie.
            old = db.get(Session, digest(request.cookies.get(cfg.cookie_name, "")))
            if old:
                old.revoked_at = utcnow()
            token, session = new_session(db, user, cfg)
            audit(db, user.id, "auth.login")
            db.commit()
            from .security import Principal
            set_cookie(response, token)
            return session_view(db, Principal(user, session, token))

    @app.get("/api/v1/auth/me", tags=["Authentication"])
    def me(request: Request):
        with database.session() as db:
            return session_view(db, principal(request, db))

    @app.post("/api/v1/auth/logout", status_code=204, tags=["Authentication"])
    def logout(request: Request, response: Response):
        with database.session() as db:
            identity = principal(request, db, mutate=True)
            identity.session.revoked_at = utcnow()
            audit(db, identity.user.id, "auth.logout")
            db.commit()
        response.delete_cookie(cfg.cookie_name, path="/", secure=cfg.cookie_secure, httponly=True, samesite="lax")

    @app.post("/api/v1/auth/refresh", tags=["Authentication"])
    def refresh(request: Request, response: Response):
        with database.session() as db:
            identity = principal(request, db, mutate=True)
            absolute_expiry = identity.session.expires_at
            identity.session.revoked_at = utcnow()
            token, session = new_session(db, identity.user, cfg)
            session.expires_at = absolute_expiry
            audit(db, identity.user.id, "auth.refresh")
            db.commit()
            from .security import Principal
            set_cookie(response, token)
            return session_view(db, Principal(identity.user, session, token))

    @app.get("/api/v1/sites", tags=["Sites"])
    def sites(request: Request, environment: Literal["simulation"]):
        with database.session() as db:
            identity = principal(request, db)
            return {"items": session_view(db, identity)["sites"], "next_cursor": None, "environment": environment}

    @app.get("/api/v1/dashboard", tags=["Dashboard"])
    def summary(request: Request, site_id: UUID, environment: Literal["simulation"]):
        with database.session() as db:
            scope(db, request, site_id, environment)
            return dashboard(db, str(site_id), cfg)

    @app.get("/api/v1/devices", tags=["Devices"])
    @app.get("/api/v1/gates", tags=["Gates"])
    def devices(request: Request, site_id: UUID, environment: Literal["simulation"]):
        with database.session() as db:
            scope(db, request, site_id, environment, "gate.read" if request.url.path.endswith("gates") else "device.read")
            query = select(Device).where(Device.site_id == str(site_id)).order_by(Device.code)
            if request.url.path.endswith("gates"):
                query = query.where(Device.node_type == "gate")
            return {"items": [device_view(d, cfg) for d in db.scalars(query.limit(100))], "next_cursor": None, "environment": environment}

    @app.get("/api/v1/devices/{device_id}", tags=["Devices"])
    @app.get("/api/v1/devices/{device_id}/health", tags=["Devices"])
    @app.get("/api/v1/gates/{device_id}/status", tags=["Gates"])
    def device_detail(request: Request, device_id: UUID):
        with database.session() as db:
            _, device = require_device(db, request, device_id)
            return device_view(device, cfg)

    @app.get("/api/v1/telemetry/latest", tags=["Telemetry"])
    def latest(request: Request, site_id: UUID, environment: Literal["simulation"]):
        with database.session() as db:
            scope(db, request, site_id, environment, "telemetry.read")
            return {"items": [device_view(d, cfg) for d in db.scalars(select(Device).where(Device.site_id == str(site_id)).order_by(Device.code))]}

    @app.get("/api/v1/telemetry/history", tags=["Telemetry"])
    def history(request: Request, site_id: UUID, environment: Literal["simulation"], metric: Literal["water_level_m", "water_level_down_m", "flow_lps", "gate_position_pct", "battery_pct", "battery_voltage", "rssi_dbm", "snr_db"] = "water_level_m", device_id: UUID | None = None, start: datetime = Query(alias="from"), end: datetime = Query(alias="to"), limit: int = Query(default=100, ge=1, le=100), cursor: str | None = Query(default=None, max_length=300)):
        if start.tzinfo is None or end.tzinfo is None or not timedelta(0) < end-start <= timedelta(days=31):
            raise HTTPException(422, detail={"code": "INVALID_TIME_RANGE", "message": "Gunakan timestamp berzona dengan rentang maksimum 31 hari."})
        with database.session() as db:
            identity = scope(db, request, site_id, environment, "telemetry.read")
            query = select(Reading).where(Reading.site_id == str(site_id), Reading.metric == metric, Reading.observed_at >= start, Reading.observed_at < end)
            if device_id:
                device = db.get(Device, str(device_id))
                if not device or device.site_id != str(site_id):
                    raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Perangkat tidak ditemukan pada lokasi ini."})
                query = query.where(Reading.device_id == str(device_id))
            if cursor:
                try:
                    at, rid = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                    at = datetime.fromisoformat(at)
                    UUID(rid)
                    if at.tzinfo is None:
                        raise ValueError()
                except Exception:
                    raise HTTPException(422, detail={"code": "INVALID_CURSOR", "message": "Cursor histori tidak valid."})
                query = query.where(or_(Reading.observed_at < at, and_(Reading.observed_at == at, Reading.id < rid)))
            rows = list(db.scalars(query.order_by(Reading.observed_at.desc(), Reading.id.desc()).limit(limit+1)))
            more, rows = len(rows) > limit, rows[:limit]
            next_cursor = base64.urlsafe_b64encode(json.dumps([timestamp(rows[-1].observed_at), rows[-1].id]).encode()).decode() if more else None
            return {"items": [{"id": r.id, "device_id": r.device_id, "site_id": r.site_id, "observed_at": timestamp(r.observed_at), "metric": r.metric, "value": r.value, "unit": r.unit, "quality": r.quality, "raw_reference": r.raw_id, "environment": "simulation"} for r in rows], "next_cursor": next_cursor, "limit": limit}

    @app.get("/api/v1/alerts", tags=["Alerts"])
    def alerts(request: Request, site_id: UUID, environment: Literal["simulation"]):
        with database.session() as db:
            scope(db, request, site_id, environment, "alerts.read")
            return {"items": [{"id": a.id, "device_id": a.device_id, "site_id": a.site_id, "code": a.code, "severity": a.severity, "title": a.title, "evidence": a.evidence, "suggested_action": a.suggested_action, "observed_at": timestamp(a.observed_at), "status": a.status, "advisory": True, "environment": "simulation"} for a in db.scalars(select(Alert).where(Alert.site_id == str(site_id)).order_by(Alert.observed_at.desc()).limit(100))], "next_cursor": None}

    @app.post("/api/v1/alerts/{alert_id}/acknowledge", tags=["Alerts"])
    def acknowledge(alert_id: UUID, body: Acknowledge, request: Request, idempotency_key: UUID = Header(alias="Idempotency-Key")):
        with database.session() as db:
            identity = principal(request, db, mutate=True)
            alert = db.get(Alert, str(alert_id))
            if not alert:
                raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Peringatan tidak ditemukan."})
            authorize(db, identity, alert.site_id, "alerts.acknowledge")
            previous, fingerprint = idempotency(db, identity, idempotency_key, "alerts.acknowledge", alert.id, body.model_dump())
            if previous:
                return previous.result
            note = AlertAcknowledgement(alert_id=alert.id, actor_id=identity.user.id, note=body.note)
            db.add(note)
            alert.status = "ACKNOWLEDGED"
            result = {"id": alert.id, "status": "ACKNOWLEDGED", "message": "Pengakuan dicatat. Tidak mengirim ACK_FAULT atau perintah aktuasi."}
            db.add(MutationKey(actor_id=identity.user.id, key=str(idempotency_key), payload_hash=fingerprint, result=result))
            audit(db, identity.user.id, "alerts.acknowledge", alert.site_id, detail={"alert_id": alert.id})
            db.commit()
            app.state.versions[alert.site_id] = app.state.versions.get(alert.site_id, 0) + 1
            return result

    @app.get("/api/v1/ledger/verify", tags=["Ledger"])
    def verify(request: Request, site_id: UUID, environment: Literal["simulation"]):
        with database.session() as db:
            scope(db, request, site_id, environment, "ledger.read")
            return verify_ledger(db, str(site_id))

    @app.get("/api/v1/ledger", tags=["Ledger"])
    def ledger(request: Request, site_id: UUID, environment: Literal["simulation"], limit: int = Query(default=25, ge=1, le=100), cursor: int | None = Query(default=None, ge=1)):
        with database.session() as db:
            scope(db, request, site_id, environment, "ledger.read")
            query = select(LedgerEntry).where(LedgerEntry.site_id == str(site_id))
            if cursor:
                query = query.where(LedgerEntry.chain_index < cursor)
            rows = list(db.scalars(query.order_by(LedgerEntry.chain_index.desc()).limit(limit+1)))
            more, rows = len(rows)>limit, rows[:limit]
            return {"items": [{"id": r.id, "site_id": r.site_id, "chain_index": r.chain_index, "occurred_at": timestamp(r.occurred_at), "payload": r.payload, "previous_hash": r.previous_hash, "current_hash": r.current_hash, "environment": "simulation"} for r in rows], "next_cursor": rows[-1].chain_index if more else None}

    @app.post("/api/v1/simulation/devices/{device_id}/scenario", tags=["Simulation"])
    def scenario(device_id: UUID, body: ScenarioChange, request: Request, idempotency_key: UUID = Header(alias="Idempotency-Key")):
        with database.session() as db:
            identity, device = require_device(db, request, device_id, "simulation.manage", mutate=True)
            previous, fingerprint = idempotency(db, identity, idempotency_key, "simulation.scenario", device.id, body.model_dump())
            if previous:
                return previous.result
            device.scenario = body.scenario
            if body.scenario in {"device_offline", "communication_failure"}:
                device.latest_received_at = utcnow()-timedelta(seconds=cfg.offline_seconds+1)
            result = {"device_id": device.id, "scenario": device.scenario, "environment": "simulation", "message": "Skenario simulator diubah; bukan command perangkat fisik."}
            db.add(MutationKey(actor_id=identity.user.id, key=str(idempotency_key), payload_hash=fingerprint, result=result))
            audit(db, identity.user.id, "simulation.scenario", device.site_id, detail={"device_id": device.id, "scenario": device.scenario})
            db.commit()
            app.state.versions[device.site_id] = app.state.versions.get(device.site_id, 0) + 1
            return result

    @app.get("/api/v1/admin/users", tags=["Administration"])
    def users(request: Request, site_id: UUID, environment: Literal["simulation"]):
        with database.session() as db:
            scope(db, request, site_id, environment, "users.read")
            return {"items": [{"id": u.id, "display_name": u.display_name, "email": u.email, "active": u.active, "roles": list(db.scalars(select(UserRole.role_code).where(UserRole.user_id == u.id, UserRole.site_id == str(site_id))))} for u in db.scalars(select(User).join(SiteAccess).where(SiteAccess.site_id == str(site_id)).order_by(User.email))]}

    @app.get("/api/v1/admin/audit", tags=["Administration"])
    def audit_history(request: Request, site_id: UUID, environment: Literal["simulation"], limit: int = Query(default=25, ge=1, le=100)):
        with database.session() as db:
            scope(db, request, site_id, environment, "audit.read")
            return {"items": [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "outcome": a.outcome, "detail": a.detail, "occurred_at": timestamp(a.occurred_at)} for a in db.scalars(select(AuditEvent).where(AuditEvent.site_id == str(site_id)).order_by(AuditEvent.occurred_at.desc()).limit(limit))]}

    @app.websocket("/ws/v1/sites/{site_id}")
    async def realtime(socket: WebSocket, site_id: UUID, environment: Literal["simulation"]):
        if socket.headers.get("origin") not in cfg.allowed_origins:
            await socket.close(code=1008)
            return
        token = socket.cookies.get(cfg.cookie_name)
        with database.session() as db:
            identity = principal_from_token(db, token, cfg)
            if not identity:
                await socket.close(code=1008)
                return
            try:
                authorize(db, identity, str(site_id))
            except HTTPException:
                await socket.close(code=1008)
                return
        await socket.accept()
        version = -1
        try:
            while True:
                with database.session() as db:
                    identity = principal_from_token(db, token, cfg)
                    if not identity:
                        await socket.close(code=1008)
                        return
                    try:
                        authorize(db, identity, str(site_id))
                    except HTTPException:
                        await socket.close(code=1008)
                        return
                current = app.state.versions.get(str(site_id), 0)
                if current != version:
                    await socket.send_json({"event_id": uid(), "type": "telemetry.updated", "site_id": str(site_id), "environment": environment, "version": current, "committed_at": timestamp(utcnow())})
                    version = current
                try:
                    message = await asyncio.wait_for(socket.receive_text(), timeout=1)
                    if len(message) > 256:
                        await socket.close(code=1009)
                        return
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            pass

    return app


app = create_app()
