"""SecLyst control-plane configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    data_dir: Path = ROOT / "data"
    database_path: Path = ROOT / "data" / "seclyst.db"
    durable_jobs_enabled: bool = False
    provider_broker_enabled: bool = False
    artifact_max_bytes: int = 100 * 1024 * 1024
    job_lease_seconds: int = 30
    auth_enabled: bool = True
    session_ttl_seconds: int = 8 * 60 * 60

    @classmethod
    def from_environment(cls) -> "Settings":
        data_dir = Path(os.getenv("SECLYST_DATA_DIR", str(ROOT / "data"))).expanduser().resolve()
        database_path = Path(
            os.getenv("SECLYST_DATABASE_PATH", str(data_dir / "seclyst.db"))
        ).expanduser().resolve()
        return cls(
            data_dir=data_dir,
            database_path=database_path,
            durable_jobs_enabled=env_bool("SECLYST_DURABLE_JOBS", True),
            provider_broker_enabled=env_bool("SECLYST_PROVIDER_BROKER", True),
            artifact_max_bytes=max(1024, int(os.getenv("SECLYST_ARTIFACT_MAX_BYTES", str(100 * 1024 * 1024)))),
            job_lease_seconds=max(5, int(os.getenv("SECLYST_JOB_LEASE_SECONDS", "30"))),
            auth_enabled=env_bool("SECLYST_AUTH", True),
            session_ttl_seconds=max(60, int(os.getenv("SECLYST_SESSION_TTL_SECONDS", str(8 * 60 * 60)))),
        )
