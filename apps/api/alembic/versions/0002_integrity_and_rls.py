"""Append-only evidence and PostgreSQL least-privilege runtime roles.

SQLite uses immutable evidence triggers; PostgreSQL also enforces site RLS.
Passwords are installed separately by the deployment bootstrap, never here.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None

IMMUTABLE = ["ledger_entries", "audit_events", "telemetry_raw", "alert_acknowledgements"]
TENANT_TABLES = ["sites", "devices", "telemetry_raw", "sensor_readings", "alerts", "ledger_entries", "audit_events"]


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in IMMUTABLE:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only'); END")
        return
    op.execute("""CREATE FUNCTION subako_deny_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only'; END $$""")
    for table in IMMUTABLE:
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION subako_deny_rewrite()")
    for role in ("subako_api", "subako_ingest"):
        op.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; END IF; END $$")
    op.execute("GRANT USAGE ON SCHEMA public TO subako_api, subako_ingest")
    op.execute("GRANT SELECT ON users, roles, permissions, role_permissions, user_roles, user_site_access, sessions, login_attempts, mutation_keys, sites, devices, telemetry_raw, sensor_readings, alerts, ledger_entries, audit_events, alert_acknowledgements, alembic_version TO subako_api")
    op.execute("GRANT INSERT, UPDATE ON sessions TO subako_api")
    op.execute("GRANT INSERT ON login_attempts, mutation_keys, audit_events, alert_acknowledgements TO subako_api")
    op.execute("GRANT UPDATE (status) ON alerts TO subako_api")
    op.execute("GRANT UPDATE (scenario, latest_received_at) ON devices TO subako_api")
    op.execute("GRANT SELECT ON sites, devices, telemetry_raw, sensor_readings, alerts, ledger_entries, alembic_version TO subako_ingest")
    op.execute("GRANT INSERT ON telemetry_raw, sensor_readings, alerts, ledger_entries, audit_events TO subako_ingest")
    op.execute("GRANT UPDATE (ledger_head, ledger_index) ON sites TO subako_ingest")
    op.execute("GRANT UPDATE (mode, latest, latest_observed_at, latest_received_at) ON devices TO subako_ingest")
    op.execute("CREATE FUNCTION subako_can_access(requested_site text) RETURNS boolean LANGUAGE sql STABLE AS $$ SELECT EXISTS (SELECT 1 FROM user_site_access WHERE user_id = current_setting('subako.user_id', true) AND site_id = requested_site) $$")
    for table in TENANT_TABLES:
        site_column = "id" if table == "sites" else "site_id"
        condition = f"subako_can_access({site_column})"
        if table == "audit_events":
            condition = f"({site_column} IS NULL OR {condition})"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY api_site_scope ON {table} TO subako_api USING ({condition}) WITH CHECK ({condition})")
        op.execute(f"CREATE POLICY ingest_site_scope ON {table} TO subako_ingest USING (true) WITH CHECK (true)")
    # Ack rows derive site from their immutable parent alert.
    op.execute("ALTER TABLE alert_acknowledgements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alert_acknowledgements FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY api_alert_scope ON alert_acknowledgements TO subako_api USING (EXISTS (SELECT 1 FROM alerts a WHERE a.id=alert_id AND subako_can_access(a.site_id))) WITH CHECK (EXISTS (SELECT 1 FROM alerts a WHERE a.id=alert_id AND subako_can_access(a.site_id)))")


def downgrade():
    raise RuntimeError("Integrity migration tidak di-downgrade dengan menghapus histori. Gunakan runbook restore/cutback.")
