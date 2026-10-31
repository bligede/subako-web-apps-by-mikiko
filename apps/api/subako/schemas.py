from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Quality = Literal["OK", "SUSPECT", "BAD", "MISSING", "FROZEN", "OUT_OF_CAL"]
Scenario = Literal["normal", "sensor_error", "device_offline", "low_battery", "overcurrent", "position_mismatch", "communication_failure"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower()


class Acknowledge(StrictModel):
    note: str = Field(min_length=3, max_length=1000)


class ScenarioChange(StrictModel):
    scenario: Scenario


class Telemetry(StrictModel):
    source_event_id: UUID
    device_id: UUID
    ts: datetime
    seq: int = Field(ge=0, le=65535)
    mode: Literal["BOOT", "IDLE", "AUTO", "MANUAL", "HOLD", "FAULT"]
    water_level_m: float | None = Field(default=None, ge=-1, le=10, allow_inf_nan=False)
    water_level_down_m: float | None = Field(default=None, ge=-1, le=10, allow_inf_nan=False)
    flow_lps: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    gate_position_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    battery_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    battery_voltage: float = Field(ge=0, le=60, allow_inf_nan=False)
    rssi_dbm: float = Field(ge=-150, le=0, allow_inf_nan=False)
    snr_db: float = Field(ge=-30, le=30, allow_inf_nan=False)
    quality: dict[str, Quality]
    environment: Literal["simulation"] = "simulation"

    @model_validator(mode="after")
    def quality_and_clock(self):
        if self.ts.tzinfo is None:
            raise ValueError("Timestamp harus menyertakan zona waktu.")
        if set(self.quality) != {"level", "flow", "encoder"}:
            raise ValueError("Quality wajib memuat level, flow, encoder.")
        return self
