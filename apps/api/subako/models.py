from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, uid, utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    authorization_version: Mapped[int] = mapped_column(Integer, default=1)


class Role(Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(24), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))


class Permission(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(80), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permissions.code"), primary_key=True)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(180))
    environment: Mapped[str] = mapped_column(String(16), default="simulation")
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Makassar")
    area_ha: Mapped[float] = mapped_column(Float)
    ledger_head: Mapped[str] = mapped_column(String(64), default="0" * 64)
    ledger_index: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("environment = 'simulation'", name="simulation_only"),)


class SiteAccess(Base):
    __tablename__ = "user_site_access"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), primary_key=True)
    __table_args__ = (ForeignKeyConstraint(["user_id", "site_id"], ["user_site_access.user_id", "user_site_access.site_id"]),)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    authorization_version: Mapped[int] = mapped_column(Integer)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    bucket: Mapped[str] = mapped_column(String(64), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MutationKey(Base):
    __tablename__ = "mutation_keys"
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    node_type: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list] = mapped_column(JSON)
    firmware_version: Mapped[str] = mapped_column(String(40), default="simulation-v0.1")
    calibration_version: Mapped[str] = mapped_column(String(40), default="DEMO-CAL-01")
    scenario: Mapped[str] = mapped_column(String(32), default="normal")
    mode: Mapped[str] = mapped_column(String(16), default="IDLE")
    latest_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("id", "site_id", name="device_site_identity"),)


class TelemetryRaw(Base):
    __tablename__ = "telemetry_raw"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    device_id: Mapped[str] = mapped_column(String(36), index=True)
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    source_event_id: Mapped[str] = mapped_column(String(36), unique=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(24), default="SIMULATION")
    __table_args__ = (ForeignKeyConstraint(["device_id", "site_id"], ["devices.id", "devices.site_id"]),)


class Reading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    raw_id: Mapped[str] = mapped_column(ForeignKey("telemetry_raw.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(36), index=True)
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    quality: Mapped[str] = mapped_column(String(24))
    __table_args__ = (ForeignKeyConstraint(["device_id", "site_id"], ["devices.id", "devices.site_id"]),)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    device_id: Mapped[str] = mapped_column(String(36))
    code: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(140))
    evidence: Mapped[dict] = mapped_column(JSON)
    suggested_action: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    __table_args__ = (ForeignKeyConstraint(["device_id", "site_id"], ["devices.id", "devices.site_id"]),)


class AlertAcknowledgement(Base):
    __tablename__ = "alert_acknowledgements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    chain_index: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)
    previous_hash: Mapped[str] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("site_id", "chain_index", name="ledger_chain_sequence"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"))
    action: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(16))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
