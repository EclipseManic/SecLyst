from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from seclyst.database.migrations import upgrade_database
from seclyst.database.session import Database


def test_initial_migration_creates_job_kernel(tmp_path) -> None:
    path = tmp_path / "migrated.db"
    assert upgrade_database(path, backup=False) is None
    database = Database(path)
    try:
        tables = set(inspect(database.engine).get_table_names())
        assert {
            "alembic_version", "jobs", "job_inputs", "job_outputs", "job_events", "job_consumers",
            "cache_entries", "provider_policies", "provider_requests", "provider_rate_state",
        } <= tables
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002_provider_broker"
    finally:
        database.dispose()
    assert upgrade_database(path, backup=True) is None
    assert not (tmp_path / "backups").exists()


def test_initial_migration_can_downgrade_cleanly(tmp_path) -> None:
    path = tmp_path / "rollback.db"
    upgrade_database(path, backup=False)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{path.as_posix()}")
    command.downgrade(config, "base")
    database = Database(path)
    try:
        assert "jobs" not in inspect(database.engine).get_table_names()
    finally:
        database.dispose()
