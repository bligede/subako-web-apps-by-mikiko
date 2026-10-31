import os
from datetime import timedelta
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from .config import Settings
from .db import Database, utcnow
from .models import User, Role, Permission, RolePermission, Site, SiteAccess, UserRole, Device
from .security import password_hasher, audit
from .services import ingest, append_ledger
from .simulator import sample

READ = {"dashboard.read", "telemetry.read", "gate.read", "ledger.read", "alerts.read", "device.read"}
ROLE_PERMISSIONS = {"viewer": READ, "operator": READ | {"alerts.acknowledge"}, "pekaseh": READ | {"alerts.acknowledge"}, "admin": READ | {"alerts.acknowledge", "simulation.manage", "users.read", "audit.read"}}
ROLE_LABELS = {"viewer": "Petani / Viewer", "operator": "Operator", "pekaseh": "Pekaseh", "admin": "Administrator teknis"}


def stable(name):
    return str(uuid5(NAMESPACE_URL, "subako-demo:" + name))


def seed(database, password, settings):
    if settings.app_env not in {"development", "testing"}:
        raise RuntimeError("Demo seed hanya untuk development/testing.")
    if not password or len(password) < 14:
        raise ValueError("Demo password harus disediakan dan minimal 14 karakter.")
    with database.session.begin() as db:
        if db.scalar(select(Site.id).limit(1)):
            return False
        for code, label in ROLE_LABELS.items():
            db.add(Role(code=code, label=label))
        for permission in sorted(set.union(*ROLE_PERMISSIONS.values())):
            db.add(Permission(code=permission))
        db.flush()
        for role, permissions in ROLE_PERMISSIONS.items():
            for permission in permissions:
                db.add(RolePermission(role_code=role, permission_code=permission))
        sites = [Site(id=stable("sembung"), name="Subak Sembung", location="Peguyangan · Denpasar Utara", area_ha=115), Site(id=stable("kedewatan"), name="Subak Kedewatan", location="Kedewatan · Gianyar", area_ha=82)]
        db.add_all(sites)
        for role in ROLE_LABELS:
            db.add(User(id=stable(role), email=f"{role}@demo.subako.local", display_name={"pekaseh": "Ni Luh Purnami", "operator": "I Made Arta", "viewer": "I Wayan Sari", "admin": "Tim Mikiko"}[role], password_hash=password_hasher.hash(password)))
        db.flush()
        for role in ROLE_LABELS:
            # Viewer intentionally has just one site, to demonstrate isolation.
            for site in sites[:1] if role == "viewer" else sites:
                db.add(SiteAccess(user_id=stable(role), site_id=site.id))
                db.flush()
                db.add(UserRole(user_id=stable(role), site_id=site.id, role_code=role))
        for index, site in enumerate(sites):
            for number, name in [(1, "Pintu Bagi Utama"), (2, "Pintu Tempek Munduk"), (3, "Pintu Petak Selatan"), (4, "Node Ukur Hulu")]:
                db.add(Device(id=stable(f"{site.id}:{number}"), site_id=site.id, code=f"SIM-{index+1}-{'GATE' if number<4 else 'MEASURE'}-{number:02}", name=name, node_type="gate" if number < 4 else "measure", channel=["Saluran primer · B-01", "Saluran sekunder · B-02", "Saluran tersier · B-03", "Saluran hulu · U-01"][number-1], capabilities=["level", "flow", "battery"]+(["position", "mode"] if number<4 else []), scenario="low_battery" if number == 2 else "device_offline" if number == 3 else "normal"))
        db.flush()
        now = utcnow()
        for device in db.scalars(select(Device).order_by(Device.id)):
            for step in range(37):
                observed = now-timedelta(minutes=(36-step)*20)
                if device.scenario == "device_offline" and step == 36:
                    continue
                ingest(db, sample(device, step, observed), emit_ledger=False)
            if device.scenario == "device_offline":
                device.latest_received_at = now-timedelta(seconds=120)
            append_ledger(db, device.site_id, {"kind": "SIMULATION_SEED", "title": f"Perangkat demo {device.code} terdaftar", "device_id": device.id, "source": "SIMULATION", "measured_volume_m3": None})
        audit(db, None, "simulation.seed", detail={"sites": 2, "devices": 8, "source": "SIMULATION"})
    return True


if __name__ == "__main__":
    cfg = Settings()
    changed = seed(Database(cfg.database_url), os.environ.get("SUBAKO_DEMO_PASSWORD"), cfg)
    print("Demo seed dibuat." if changed else "Seed sudah ada; tidak mengubah akun atau histori.")
