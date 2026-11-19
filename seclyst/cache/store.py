from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..database.models import CacheEntry
from ..database.session import Database


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class CachedValue:
    value: dict[str, Any]
    state: str
    created_at: datetime
    expires_at: datetime
    stale: bool
    hit_count: int


class CacheStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, key: str, *, allow_stale: bool = True) -> CachedValue | None:
        now = utcnow()
        with self.database.session() as session, session.begin():
            entry = session.get(CacheEntry, key)
            if entry is None or entry.status == "invalidated":
                return None
            expires_at = aware(entry.expires_at)
            stale_until = aware(entry.stale_until)
            stale = expires_at <= now
            if stale and (not allow_stale or stale_until <= now):
                return None
            entry.hit_count += 1
            entry.last_accessed_at = now
            return CachedValue(
                value=json.loads(entry.value_json),
                state=entry.status,
                created_at=aware(entry.created_at),
                expires_at=expires_at,
                stale=stale,
                hit_count=entry.hit_count,
            )

    def put(
        self,
        key: str,
        value: dict[str, Any],
        *,
        producer: str,
        ttl_seconds: int,
        stale_seconds: int,
        status: str = "fresh",
        producer_version: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CacheEntry:
        now = utcnow()
        with self.database.session() as session, session.begin():
            entry = session.get(CacheEntry, key) or CacheEntry(cache_key=key)
            entry.namespace = "provider.response"
            entry.status = status
            entry.value_json = json.dumps(value, sort_keys=True, separators=(",", ":"))
            entry.producer = producer
            entry.producer_version = producer_version
            entry.created_at = now
            entry.expires_at = now + timedelta(seconds=max(0, ttl_seconds))
            entry.stale_until = entry.expires_at + timedelta(seconds=max(0, stale_seconds))
            entry.last_accessed_at = now
            entry.hit_count = 0
            entry.metadata_json = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
            session.add(entry)
            session.flush()
            return entry

    def invalidate(self, key: str) -> bool:
        with self.database.session() as session, session.begin():
            entry = session.get(CacheEntry, key)
            if entry is None:
                return False
            entry.status = "invalidated"
            return True
