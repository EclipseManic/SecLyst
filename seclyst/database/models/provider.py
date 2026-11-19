from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    value_json: Mapped[str] = mapped_column(Text)
    producer: Mapped[str] = mapped_column(String(64))
    producer_version: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stale_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class ProviderPolicy(Base):
    __tablename__ = "provider_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(96))
    requests_per_minute: Mapped[int] = mapped_column(Integer, default=4)
    requests_per_day: Mapped[int] = mapped_column(Integer, default=500)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    max_safe_retries: Mapped[int] = mapped_column(Integer, default=1)
    positive_ttl_seconds: Mapped[int] = mapped_column(Integer, default=21600)
    negative_ttl_seconds: Mapped[int] = mapped_column(Integer, default=900)
    stale_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    submission_requires_approval: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (UniqueConstraint("provider", "operation", name="uq_provider_policy"),)


class ProviderRequest(Base):
    __tablename__ = "provider_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(96), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_entry_key: Mapped[str | None] = mapped_column(ForeignKey("cache_entries.cache_key"), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)


class ProviderRateState(Base):
    __tablename__ = "provider_rate_state"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation: Mapped[str] = mapped_column(String(96), primary_key=True)
    minute_window_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    minute_count: Mapped[int] = mapped_column(Integer, default=0)
    day_window_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    day_count: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
