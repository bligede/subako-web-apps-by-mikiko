import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from fastapi import Request, HTTPException
from sqlalchemy import select, text
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from .db import utcnow, aware
from .models import User, Session, SiteAccess, UserRole, RolePermission, AuditEvent

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token):
    return digest("SUBAKO-CSRF:" + token)


def set_principal_context(db, user_id):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT set_config('subako.user_id', :user_id, true)"), {"user_id": user_id})


def verify_password(encoded, password):
    try:
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def audit(db, actor, action, site_id=None, outcome="SUCCESS", detail=None):
    db.add(AuditEvent(actor_id=actor, action=action, site_id=site_id, outcome=outcome, detail=detail or {}))


@dataclass
class Principal:
    user: User
    session: Session
    token: str


def principal_from_token(db, token, cfg, touch=False):
    if not token:
        return None
    session = db.get(Session, digest(token))
    now = utcnow()
    if not session or session.revoked_at or aware(session.expires_at) <= now or aware(session.last_seen_at) + timedelta(seconds=cfg.session_idle_seconds) <= now:
        return None
    user = db.get(User, session.user_id)
    if not user or not user.active or user.authorization_version != session.authorization_version:
        return None
    if touch and aware(session.last_seen_at) + timedelta(seconds=30) < now:
        session.last_seen_at = now
        db.commit()
    set_principal_context(db, user.id)
    return Principal(user, session, token)


def principal(request: Request, db, mutate=False):
    cfg = request.app.state.settings
    identity = principal_from_token(db, request.cookies.get(cfg.cookie_name), cfg, touch=True)
    if identity is None:
        raise HTTPException(401, detail={"code": "SESSION_REQUIRED", "message": "Sesi berakhir. Silakan masuk kembali."})
    if mutate:
        token = request.headers.get("x-csrf-token", "")
        if not token or not secrets.compare_digest(digest(token), identity.session.csrf_hash):
            raise HTTPException(403, detail={"code": "CSRF_DENIED", "message": "Token keamanan tidak valid."})
    return identity


def permissions(db, user_id, site_id):
    return set(db.scalars(select(RolePermission.permission_code).join(UserRole, RolePermission.role_code == UserRole.role_code).where(UserRole.user_id == user_id, UserRole.site_id == site_id)))


def authorize(db, identity, site_id, permission="dashboard.read"):
    access = db.get(SiteAccess, (identity.user.id, site_id))
    if not access:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lokasi atau sumber daya tidak ditemukan."})
    if permission not in permissions(db, identity.user.id, site_id):
        raise HTTPException(403, detail={"code": "PERMISSION_DENIED", "message": "Peran Anda tidak berwenang melakukan tindakan ini."})


def new_session(db, user, cfg):
    token = secrets.token_urlsafe(32)
    session = Session(token_hash=digest(token), user_id=user.id, csrf_hash=digest(csrf_for(token)), expires_at=utcnow()+timedelta(seconds=cfg.session_absolute_seconds), last_seen_at=utcnow(), authorization_version=user.authorization_version)
    db.add(session)
    return token, session
