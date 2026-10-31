import hashlib
import json
from datetime import timedelta
from sqlalchemy import select, func
from .db import aware, utcnow, uid
from .models import Device, TelemetryRaw, Reading, Site, LedgerEntry, Alert

METRICS = {"water_level_m": ("m", "level"), "water_level_down_m": ("m", "level"), "flow_lps": ("L/s", "flow"), "gate_position_pct": ("%", "encoder"), "battery_pct": ("%", None), "battery_voltage": ("V", None), "rssi_dbm": ("dBm", None), "snr_db": ("dB", None)}
ALERTS = {
    "LOW_BATTERY": ("warning", "Baterai perangkat rendah", "Periksa panel surya, konektor, dan pengisian baterai."),
    "DEVICE_OFFLINE": ("critical", "Perangkat tidak terhubung", "Periksa catu daya dan komunikasi. Operasi mekanis tetap tersedia."),
    "SENSOR_ERROR": ("warning", "Kualitas sensor bermasalah", "Periksa sensor dan kalibrasi; jangan gunakan nilai invalid untuk keputusan."),
    "OVERCURRENT": ("critical", "Arus motor berlebih", "Lakukan pemeriksaan fisik dan prosedur keselamatan setempat."),
    "POSITION_MISMATCH": ("critical", "Feedback posisi tidak sesuai", "Periksa encoder, mekanik, dan interlock di lokasi."),
    "COMMUNICATION_FAILURE": ("critical", "Gangguan komunikasi", "Periksa gateway dan koneksi radio."),
}


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def timestamp(value):
    return aware(value).isoformat().replace("+00:00", "Z") if value else None


def connectivity(device, cfg):
    if device.latest_received_at is None:
        return "OFFLINE"
    age = (utcnow() - aware(device.latest_received_at)).total_seconds()
    return "OFFLINE" if age > cfg.offline_seconds else "STALE" if age > cfg.stale_seconds else "ONLINE"


def device_view(device, cfg):
    snapshot = device.latest or {}
    return {"id": device.id, "site_id": device.site_id, "environment": "simulation", "code": device.code, "name": device.name, "node_type": device.node_type, "channel": device.channel, "capabilities": device.capabilities, "firmware_version": device.firmware_version, "calibration_version": device.calibration_version, "scenario": device.scenario, "mode": device.mode, "connectivity": connectivity(device, cfg), "observed_at": timestamp(device.latest_observed_at), "received_at": timestamp(device.latest_received_at), "quality": snapshot.get("quality", {}), **{metric: snapshot.get(metric) for metric in METRICS}}


def append_ledger(db, site_id, payload, occurred_at=None):
    # Lock the chain head before assigning an index. SQLite serializes writes;
    # PostgreSQL uses a row lock. Unique(site,index) independently prevents forks.
    site = db.scalar(select(Site).where(Site.id == site_id).with_for_update().execution_options(populate_existing=True))
    index = site.ledger_index + 1
    at = occurred_at or utcnow()
    body = {"schema_version": 1, "site_id": site_id, "environment": "simulation", "chain_index": index, "occurred_at": timestamp(at), "data": payload}
    current = hashlib.sha256(bytes.fromhex(site.ledger_head) + canonical(body).encode()).hexdigest()
    entry = LedgerEntry(site_id=site_id, chain_index=index, occurred_at=at, payload=body, previous_hash=site.ledger_head, current_hash=current)
    db.add(entry)
    site.ledger_head = current
    site.ledger_index = index
    db.flush()
    return entry


def verify_ledger(db, site_id):
    entries = list(db.scalars(select(LedgerEntry).where(LedgerEntry.site_id == site_id).order_by(LedgerEntry.chain_index)))
    previous, expected, failures = "0" * 64, 1, []
    for entry in entries:
        calculated = hashlib.sha256(bytes.fromhex(previous) + canonical(entry.payload).encode()).hexdigest()
        if entry.chain_index != expected or entry.payload.get("chain_index") != expected:
            failures.append(f"GAP:{expected}")
        if entry.previous_hash != previous or entry.current_hash != calculated:
            failures.append(f"MISMATCH:{entry.chain_index}")
        previous, expected = entry.current_hash, entry.chain_index + 1
    site = db.get(Site, site_id)
    if site.ledger_head != previous or site.ledger_index != expected - 1:
        failures.append("HEAD_MISMATCH")
    return {"site_id": site_id, "environment": "simulation", "result": "MISMATCH" if failures else "VERIFIED", "checked_count": len(entries), "first_index": 1 if entries else 0, "last_index": expected - 1, "head_hash": previous, "failures": failures, "verified_at": timestamp(utcnow()), "anchor": "database_chain_head", "limitation": "Anchor saat ini di database yang sama. Independent sealing belum diimplementasikan; integritas tidak membuktikan kebenaran sensor."}


def raise_alert(db, device, code, evidence):
    existing = db.scalar(select(Alert).where(Alert.device_id == device.id, Alert.code == code, Alert.status != "RESOLVED"))
    if existing:
        return None
    severity, title, action = ALERTS[code]
    item = Alert(site_id=device.site_id, device_id=device.id, code=code, severity=severity, title=title, evidence={"environment": "SIMULATION", **evidence}, suggested_action=action)
    db.add(item)
    db.flush()
    return item


def ingest(db, payload, emit_ledger=True):
    data = payload.model_dump(mode="json")
    data_hash = hashlib.sha256(canonical(data).encode()).hexdigest()
    existing = db.scalar(select(TelemetryRaw).where(TelemetryRaw.source_event_id == str(payload.source_event_id)))
    if existing:
        if existing.payload_hash != data_hash:
            raise ValueError("SOURCE_EVENT_CONFLICT")
        return {"duplicate": True, "raw_id": existing.id}
    if aware(payload.ts) > utcnow() + timedelta(seconds=30):
        raise ValueError("FUTURE_TIMESTAMP")
    device = db.get(Device, str(payload.device_id))
    if not device:
        raise ValueError("UNREGISTERED_DEVICE")
    raw = TelemetryRaw(id=uid(), device_id=device.id, site_id=device.site_id, source_event_id=str(payload.source_event_id), observed_at=payload.ts, payload=data, payload_hash=data_hash)
    db.add(raw)
    db.flush()
    snapshot = {"quality": data["quality"]}
    for metric, (unit, key) in METRICS.items():
        quality = data["quality"][key] if key else "OK"
        value = data.get(metric)
        if quality in {"BAD", "MISSING", "FROZEN"}:
            value = None
        snapshot[metric] = value
        db.add(Reading(observed_at=payload.ts, raw_id=raw.id, device_id=device.id, site_id=device.site_id, metric=metric, value=value, unit=unit, quality=quality))
    if not device.latest_observed_at or aware(payload.ts) >= aware(device.latest_observed_at):
        previous_mode = device.mode
        device.latest, device.mode = snapshot, payload.mode
        device.latest_observed_at, device.latest_received_at = payload.ts, utcnow()
        if emit_ledger and previous_mode != payload.mode:
            append_ledger(db, device.site_id, {"kind": "MODE_CHANGE", "title": f"Mode {device.code}: {previous_mode} → {payload.mode}", "device_id": device.id, "raw_reference": raw.id, "reported_mode": payload.mode}, payload.ts)
        if payload.battery_pct < 25:
            raise_alert(db, device, "LOW_BATTERY", {"battery_pct": payload.battery_pct, "raw_reference": raw.id})
        if any(q in {"BAD", "MISSING", "FROZEN"} for q in payload.quality.values()):
            raise_alert(db, device, "SENSOR_ERROR", {"quality": data["quality"], "raw_reference": raw.id})
        for scenario, code in [("overcurrent", "OVERCURRENT"), ("position_mismatch", "POSITION_MISMATCH")]:
            if device.scenario == scenario:
                raise_alert(db, device, code, {"reported_mode": payload.mode, "raw_reference": raw.id})
    db.flush()
    return {"duplicate": False, "raw_id": raw.id, "site_id": device.site_id, "device_id": device.id}


def dashboard(db, site_id, cfg):
    devices = list(db.scalars(select(Device).where(Device.site_id == site_id).order_by(Device.code)))
    views = [device_view(d, cfg) for d in devices]
    fresh = [v for v in views if v["connectivity"] == "ONLINE"]
    levels = [v["water_level_m"] for v in fresh if v["water_level_m"] is not None and v["quality"].get("level") == "OK"]
    flows = [v["flow_lps"] for v in fresh if v["flow_lps"] is not None and v["quality"].get("flow") == "OK"]
    active_alerts = db.scalar(select(func.count()).select_from(Alert).where(Alert.site_id == site_id, Alert.status != "RESOLVED"))
    latest_at = max((aware(d.latest_received_at) for d in devices if d.latest_received_at), default=None)
    return {"site_id": site_id, "environment": "simulation", "mean_water_level_m": round(sum(levels)/len(levels), 3) if levels else None, "mean_flow_lps": round(sum(flows)/len(flows), 2) if flows else None, "online_devices": len(fresh), "total_devices": len(devices), "gate_nodes": sum(d.node_type == "gate" for d in devices), "measure_nodes": sum(d.node_type == "measure" for d in devices), "active_alerts": active_alerts, "last_received_at": timestamp(latest_at), "generated_at": timestamp(utcnow()), "freshness": {"stale_seconds": cfg.stale_seconds, "offline_seconds": cfg.offline_seconds}, "devices": views}
