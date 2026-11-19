"""Add content-addressed artifacts and result objects.

Revision ID: 0003_artifact_store
Revises: 0002_provider_broker
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_artifact_store"
down_revision: str | None = "0002_provider_broker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("quarantined", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_class", sa.String(32), nullable=False),
    )
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256"], unique=True)
    op.create_index("ix_artifacts_created_at", "artifacts", ["created_at"])
    op.create_table(
        "artifact_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("parent_artifact_id", sa.String(36), sa.ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("child_artifact_id", sa.String(36), sa.ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("relationship", sa.String(64), nullable=False),
        sa.Column("producing_job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parent_artifact_id", "child_artifact_id", "relationship", name="uq_artifact_edge"),
    )
    op.create_index("ix_artifact_edges_parent_artifact_id", "artifact_edges", ["parent_artifact_id"])
    op.create_index("ix_artifact_edges_child_artifact_id", "artifact_edges", ["child_artifact_id"])
    op.create_table(
        "result_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("schema_name", sa.String(96), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("storage_ref", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_result_objects_schema_name", "result_objects", ["schema_name"])
    op.create_index("ix_result_objects_created_at", "result_objects", ["created_at"])


def downgrade() -> None:
    op.drop_table("result_objects")
    op.drop_table("artifact_edges")
    op.drop_table("artifacts")
