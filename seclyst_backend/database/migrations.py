from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parents[2]


def upgrade_database(path: Path, *, backup: bool = True) -> Path | None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "seclyst_backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{path.as_posix()}")
    target_revision = ScriptDirectory.from_config(config).get_current_head()

    if path.is_file() and path.stat().st_size:
        engine = create_engine(f"sqlite+pysqlite:///{path.as_posix()}")
        try:
            with engine.connect() as connection:
                current_revision = MigrationContext.configure(connection).get_current_revision()
        finally:
            engine.dispose()
        if current_revision == target_revision:
            return None

    backup_path: Path | None = None
    if backup and path.is_file() and path.stat().st_size:
        backup_dir = path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backup_dir / f"{path.stem}-{timestamp}{path.suffix}"
        shutil.copy2(path, backup_path)

    command.upgrade(config, "head")
    return backup_path
