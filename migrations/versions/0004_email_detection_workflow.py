"""Add analysis runs and detection candidates."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0004_email_detection"
down_revision: str | None = "0003_artifact_store"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipe", sa.String(96), nullable=False),
        sa.Column("recipe_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("initial_job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runs_recipe", "runs", ["recipe"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])
    op.create_table(
        "detection_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("rule_source_json", sa.Text(), nullable=False),
        sa.Column("validation_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_detection_candidates_run_id", "detection_candidates", ["run_id"])
    op.create_index("ix_detection_candidates_status", "detection_candidates", ["status"])


def downgrade() -> None:
    op.drop_table("detection_candidates")
    op.drop_table("runs")
