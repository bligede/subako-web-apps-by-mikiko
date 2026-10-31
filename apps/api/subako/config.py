from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUBAKO_", env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    data_mode: Literal["simulation"] = "simulation"
    database_url: str = "sqlite:///./subako-dev.db"
    simulator_database_url: str | None = None
    cookie_secure: bool = False
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8080", "http://localhost:8080"]
    simulator_enabled: bool = True
    simulator_interval_seconds: float = 10
    stale_seconds: int = 30
    offline_seconds: int = 90
    session_idle_seconds: int = 1800
    session_absolute_seconds: int = 43200
    timescale_enabled: bool = False
    demo_password: str | None = None

    @model_validator(mode="after")
    def deployment_guards(self):
        if self.app_env in {"staging", "production"}:
            if not self.cookie_secure or not self.database_url.startswith("postgresql"):
                raise ValueError("Staging/production memerlukan cookie Secure dan PostgreSQL.")
            if self.demo_password:
                raise ValueError("Demo seed password dilarang pada staging/production.")
        if self.timescale_enabled and not self.database_url.startswith("postgresql"):
            raise ValueError("TimescaleDB memerlukan PostgreSQL.")
        return self

    @property
    def cookie_name(self):
        return "__Host-subako_session" if self.cookie_secure else "subako_dev_session"
