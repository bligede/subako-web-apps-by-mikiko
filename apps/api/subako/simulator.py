"""In-process fake devices only; no MQTT/hardware dependencies or secrets."""
import asyncio
import logging
import math
from datetime import timedelta
from sqlalchemy import select
from .db import uid, utcnow
from .models import Device
from .schemas import Telemetry
from .services import ingest, raise_alert, timestamp

log = logging.getLogger("subako.simulator")


def sample(device, step, observed_at=None):
    phase = sum(ord(c) for c in device.code) % 7
    level = round(.75 + .12 * math.sin(step / 9 + phase), 3)
    quality = {"level": "OK", "flow": "OK", "encoder": "OK"}
    mode = "MANUAL" if device.code.endswith("03") else "AUTO" if device.node_type == "gate" else "IDLE"
    battery, position = (23 if device.scenario == "low_battery" else 87), (34 + phase * 3 if device.node_type == "gate" else None)
    if device.scenario == "sensor_error":
        quality["level"] = "BAD"
        mode = "HOLD" if device.node_type == "gate" else "IDLE"
    if device.scenario in {"overcurrent", "position_mismatch"}:
        mode = "FAULT"
    if device.scenario == "position_mismatch":
        quality["encoder"] = "BAD"
    return Telemetry(source_event_id=uid(), device_id=device.id, ts=observed_at or utcnow(), seq=step % 65536, mode=mode, water_level_m=level, water_level_down_m=round(level-.18, 3), flow_lps=round(35+7*math.sin(step/12+phase), 2), gate_position_pct=position, battery_pct=battery, battery_voltage=12.1 if battery < 25 else 12.9, rssi_dbm=-71-phase, snr_db=7.2, quality=quality)


def tick(database, step):
    changed_sites = set()
    with database.session.begin() as db:
        for device in db.scalars(select(Device).order_by(Device.id)):
            if device.scenario in {"device_offline", "communication_failure"}:
                if device.latest_received_at is None:
                    device.latest_received_at = utcnow()-timedelta(seconds=120)
                raise_alert(db, device, "DEVICE_OFFLINE" if device.scenario == "device_offline" else "COMMUNICATION_FAILURE", {"last_received_at": timestamp(device.latest_received_at)})
            else:
                ingest(db, sample(device, step))
            changed_sites.add(device.site_id)
    return changed_sites


async def run(app):
    step = 0
    while True:
        try:
            sites = await asyncio.to_thread(tick, app.state.simdb, step)
            # Sockets use committed snapshots and independent sessions.
            for site_id in sites:
                app.state.versions[site_id] = app.state.versions.get(site_id, 0) + 1
            step += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Simulation tick failed; transaction rolled back")
        await asyncio.sleep(app.state.settings.simulator_interval_seconds)
