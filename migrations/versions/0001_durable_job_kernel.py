"""Add durable job kernel and ordered event journal.

Revision ID: 0001_job_kernel
Revises:
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0001_job_kernel"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tool_id", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority_class", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=96), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("result_ref", sa.String(length=512), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("client_request_id"),
    )
    op.create_index("ix_jobs_tool_id", "jobs", ["tool_id"])
    op.create_index("ix_jobs_operation", "jobs", ["operation"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_lease_expires_at", "jobs", ["lease_expires_at"])
    op.create_index(
        "uq_jobs_active_dedupe_key",
        "jobs",
        ["dedupe_key"],
        unique=True,
        sqlite_where=sa.text(
            "status IN ('queued','running','waiting_provider','waiting_rate_limit','awaiting_approval','cancelling')"
        ),
    )

    op.create_table(
        "job_inputs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("value_ref", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("job_id", "position", name="uq_job_input_position"),
    )
    op.create_index("ix_job_inputs_job_id", "job_inputs", ["job_id"])

    op.create_table(
        "job_outputs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("output_type", sa.String(length=32), nullable=False),
        sa.Column("value_ref", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("job_id", "name", name="uq_job_output_name"),
    )
    op.create_index("ix_job_outputs_job_id", "job_outputs", ["job_id"])

    op.create_table(
        "job_events",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=96), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "job_sequence", name="uq_job_event_sequence"),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index("ix_job_events_created_at", "job_events", ["created_at"])

    op.create_table(
        "job_consumers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consumer_type", sa.String(length=32), nullable=False),
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "consumer_type", "consumer_id", name="uq_job_consumer"),
    )
    op.create_index("ix_job_consumers_job_id", "job_consumers", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_consumers")
    op.drop_table("job_events")
    op.drop_table("job_outputs")
    op.drop_table("job_inputs")
    op.drop_table("jobs")
