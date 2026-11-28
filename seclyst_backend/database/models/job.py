from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


ACTIVE_STATUS_SQL = "'queued','running','waiting_provider','waiting_rate_limit','awaiting_approval','cancelling'"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tool_id: Mapped[str] = mapped_column(String(32), index=True)
    operation: Mapped[str] = mapped_column(String(96), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    priority_class: Mapped[str] = mapped_column(String(24), default="interactive")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    client_request_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), index=True)
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    configuration_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(96), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    result_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)

    inputs: Mapped[list[JobInput]] = relationship(back_populates="job", cascade="all, delete-orphan")
    outputs: Mapped[list[JobOutput]] = relationship(back_populates="job", cascade="all, delete-orphan")
    events: Mapped[list[JobEvent]] = relationship(back_populates="job", cascade="all, delete-orphan")
    consumers: Mapped[list[JobConsumer]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            "uq_jobs_active_dedupe_key",
            "dedupe_key",
            unique=True,
            sqlite_where=text(f"status IN ({ACTIVE_STATUS_SQL})"),
        ),
    )


class JobInput(Base):
    __tablename__ = "job_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    input_type: Mapped[str] = mapped_column(String(32))
    value_ref: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    job: Mapped[Job] = relationship(back_populates="inputs")

    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_job_input_position"),)


class JobOutput(Base):
    __tablename__ = "job_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(96))
    output_type: Mapped[str] = mapped_column(String(32))
    value_ref: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    job: Mapped[Job] = relationship(back_populates="outputs")

    __table_args__ = (UniqueConstraint("job_id", "name", name="uq_job_output_name"),)


class JobEvent(Base):
    __tablename__ = "job_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    job_sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str | None] = mapped_column(String(96), nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(String(512), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    job: Mapped[Job] = relationship(back_populates="events")

    __table_args__ = (UniqueConstraint("job_id", "job_sequence", name="uq_job_event_sequence"),)


class JobConsumer(Base):
    __tablename__ = "job_consumers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    consumer_type: Mapped[str] = mapped_column(String(32))
    consumer_id: Mapped[str] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    job: Mapped[Job] = relationship(back_populates="consumers")

    __table_args__ = (UniqueConstraint("job_id", "consumer_type", "consumer_id", name="uq_job_consumer"),)
