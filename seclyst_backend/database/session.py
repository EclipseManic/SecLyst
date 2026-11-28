from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .base import Base


class Database:
    def __init__(self, path: Path | str, *, create_schema: bool = False) -> None:
        path = Path(path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine = create_engine(
            f"sqlite+pysqlite:///{path.as_posix()}",
            connect_args={"check_same_thread": False, "timeout": 5},
        )
        self._configure_sqlite(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        if create_schema:
            # Unit tests use metadata directly; runtime uses Alembic.
            from . import models as _models  # noqa: F401

            Base.metadata.create_all(self.engine)

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def set_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    def session(self) -> Session:
        return self.session_factory()

    def dispose(self) -> None:
        self.engine.dispose()
