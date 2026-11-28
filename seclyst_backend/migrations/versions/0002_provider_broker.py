"""Add provider broker scheduling and cache tables.

Revision ID: 0002_provider_broker
Revises: 0001_job_kernel
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_provider_broker"
down_revision: str | None = "0001_job_kernel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cache_entries",
        sa.Column("cache_key", sa.String(length=64), primary_key=True),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("producer", sa.String(length=64), nullable=False),
        sa.Column("producer_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_cache_entries_namespace", "cache_entries", ["namespace"])
    op.create_index("ix_cache_entries_status", "cache_entries", ["status"])
    op.create_index("ix_cache_entries_expires_at", "cache_entries", ["expires_at"])

    op.create_table(
        "provider_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=96), nullable=False),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("requests_per_day", sa.Integer(), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_safe_retries", sa.Integer(), nullable=False),
        sa.Column("positive_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("negative_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("stale_seconds", sa.Integer(), nullable=False),
        sa.Column("submission_requires_approval", sa.Integer(), nullable=False),
        sa.UniqueConstraint("provider", "operation", name="uq_provider_policy"),
    )
    op.create_index("ix_provider_policies_provider", "provider_policies", ["provider"])

    op.create_table(
        "provider_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("cache_entry_key", sa.String(length=64), sa.ForeignKey("cache_entries.cache_key"), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
    )
    op.create_index("ix_provider_requests_request_key", "provider_requests", ["request_key"])
    op.create_index("ix_provider_requests_provider", "provider_requests", ["provider"])
    op.create_index("ix_provider_requests_operation", "provider_requests", ["operation"])
    op.create_index("ix_provider_requests_status", "provider_requests", ["status"])

    op.create_table(
        "provider_rate_state",
        sa.Column("provider", sa.String(length=64), primary_key=True),
        sa.Column("operation", sa.String(length=96), primary_key=True),
        sa.Column("minute_window_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minute_count", sa.Integer(), nullable=False),
        sa.Column("day_window_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day_count", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_rate_state")
    op.drop_table("provider_requests")
    op.drop_table("provider_policies")
    op.drop_table("cache_entries")
