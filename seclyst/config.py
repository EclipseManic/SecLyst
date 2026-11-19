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
    runtime_dir: Path = ROOT / "runtime"
    database_path: Path = ROOT / "runtime" / "seclyst.db"
    durable_jobs_enabled: bool = False
    job_lease_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "Settings":
        runtime_dir = Path(os.getenv("SECLYST_RUNTIME_DIR", str(ROOT / "runtime"))).expanduser().resolve()
        database_path = Path(
            os.getenv("SECLYST_DATABASE_PATH", str(runtime_dir / "seclyst.db"))
        ).expanduser().resolve()
        return cls(
            runtime_dir=runtime_dir,
            database_path=database_path,
            durable_jobs_enabled=env_bool("SECLYST_DURABLE_JOBS", False),
            job_lease_seconds=max(5, int(os.getenv("SECLYST_JOB_LEASE_SECONDS", "30"))),
        )
