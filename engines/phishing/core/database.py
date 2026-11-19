"""
Persistent SQLite storage for scan history.
Scans survive browser restarts and are only removed on user request.
"""
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path(
    os.getenv(
        "SECLYST_PHISHING_DATA_DIR",
        str(Path(__file__).resolve().parent.parent / "data"),
    )
).expanduser().resolve()
DB_PATH = DB_DIR / "scans.db"

_local = threading.local()


def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        init_db(_local.conn)
    return _local.conn


def init_db(conn=None):
    c = conn if conn is not None else _get_conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            verdict     TEXT NOT NULL,
            severity    TEXT NOT NULL,
            score       REAL NOT NULL,
            timestamp   TEXT NOT NULL,
            payload     TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp DESC)
    """)
    try:
        cursor = c.execute("PRAGMA table_info(scans)")
        cols = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()}
        required = {"id", "filename", "verdict", "severity", "score", "timestamp", "payload"}
        if cols and not required.issubset(cols):
            logger.warning("Scans table schema mismatch detected. Upgrading schema...")
            c.execute("ALTER TABLE scans RENAME TO scans_old")
            c.execute("""
                CREATE TABLE scans (
                    id          TEXT PRIMARY KEY,
                    filename    TEXT NOT NULL,
                    verdict     TEXT NOT NULL,
                    severity    TEXT NOT NULL,
                    score       REAL NOT NULL,
                    timestamp   TEXT NOT NULL,
                    payload     TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp DESC)")
    except Exception as exc:
        logger.warning("Schema check warning: %s", exc)
    c.commit()


def save_scan(filename, verdict, severity, score, payload):
    scan_id = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        payload_json = json.dumps(payload)
    except TypeError:
        payload_json = json.dumps({"error": "payload not serializable", "fallback": str(payload)[:50000]})
    conn.execute(
        "INSERT INTO scans (id, filename, verdict, severity, score, timestamp, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (scan_id, filename, verdict, severity, score, ts, payload_json),
    )
    conn.commit()
    return scan_id


def get_scan(scan_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_scans(limit=50, offset=0):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, filename, verdict, severity, score, timestamp FROM scans ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_scan(scan_id):
    conn = _get_conn()
    conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.commit()


def delete_all_scans():
    conn = _get_conn()
    conn.execute("DELETE FROM scans")
    conn.commit()


def scan_count():
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM scans").fetchone()
    return row["cnt"] if row else 0


def _row_to_dict(row):
    d = dict(row)
    if "payload" in d:
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
