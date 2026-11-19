from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database.models import Job, JobConsumer, JobEvent, JobInput
from ..database.session import Database
from .states import ACTIVE_STATUSES, JobStatus, require_transition


def utcnow() -> datetime:
    return datetime.now(UTC)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class JobInputValue:
    type: str
    ref: str
    sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobCreate:
    tool: str
    operation: str
    inputs: list[JobInputValue]
    parameters: dict[str, Any] = field(default_factory=dict)
    priority_class: str = "interactive"
    priority: int = 100
    client_request_id: str | None = None
    configuration_hash: str = ""
    max_attempts: int = 3
    force_refresh: bool = False
    consumer_type: str = "api"
    consumer_id: str = "anonymous"


@dataclass(frozen=True)
class JobCreateResult:
    job: Job
    deduplicated: bool
    attached_to_job_id: str | None


class JobNotFound(LookupError):
    pass


class JobConflict(RuntimeError):
    pass


class JobService:
    def __init__(self, database: Database, *, lease_seconds: int = 30) -> None:
        self.database = database
        self.lease_seconds = lease_seconds

    @staticmethod
    def dedupe_key(command: JobCreate) -> str:
        value = {
            "tool": command.tool,
            "operation": command.operation,
            "inputs": [
                {"type": item.type, "ref": item.ref, "sha256": item.sha256, "metadata": item.metadata}
                for item in command.inputs
            ],
            "parameters": command.parameters,
            "configuration_hash": command.configuration_hash,
        }
        return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

    def create(self, command: JobCreate) -> JobCreateResult:
        dedupe_key = self.dedupe_key(command)
        active_values = [status.value for status in ACTIVE_STATUSES]
        try:
            with self.database.session() as session, session.begin():
                existing = self._find_existing(session, command.client_request_id, dedupe_key, active_values)
                if existing is not None:
                    self._attach_consumer(session, existing.id, command.consumer_type, command.consumer_id)
                    return JobCreateResult(existing, True, existing.id)

                now = utcnow()
                job = Job(
                    id=str(uuid.uuid4()),
                    tool_id=command.tool,
                    operation=command.operation,
                    status=JobStatus.QUEUED.value,
                    priority_class=command.priority_class,
                    priority=command.priority,
                    client_request_id=command.client_request_id,
                    dedupe_key=dedupe_key,
                    parameters_json=canonical_json(command.parameters),
                    configuration_hash=command.configuration_hash,
                    max_attempts=command.max_attempts,
                    progress=0,
                    stage="queued",
                    created_at=now,
                    queued_at=now,
                )
                for position, value in enumerate(command.inputs):
                    job.inputs.append(JobInput(
                        position=position,
                        input_type=value.type,
                        value_ref=value.ref,
                        sha256=value.sha256,
                        metadata_json=canonical_json(value.metadata),
                    ))
                session.add(job)
                session.flush()
                self._attach_consumer(session, job.id, command.consumer_type, command.consumer_id)
                self._append_event(session, job, "state", "Job queued.")
                return JobCreateResult(job, False, None)
        except IntegrityError as exc:
            # A concurrent creator can win after the first lookup but before
            # this transaction flushes. Attach to that active job instead of
            # leaking an integrity error to the caller.
            with self.database.session() as session, session.begin():
                existing = self._find_existing(session, command.client_request_id, dedupe_key, active_values)
                if existing is None:
                    raise JobConflict("Job idempotency or deduplication constraint was violated.") from exc
                self._attach_consumer(session, existing.id, command.consumer_type, command.consumer_id)
                return JobCreateResult(existing, True, existing.id)

    def get(self, job_id: str) -> Job:
        with self.database.session() as session:
            job = session.scalar(
                select(Job)
                .where(Job.id == job_id)
                .options(selectinload(Job.inputs), selectinload(Job.outputs))
            )
            if job is None:
                raise JobNotFound(job_id)
            return job

    def list(self, *, status: str | None = None, tool: str | None = None, limit: int = 50) -> list[Job]:
        with self.database.session() as session:
            statement = select(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 200)))
            if status:
                statement = statement.where(Job.status == JobStatus(status).value)
            if tool:
                statement = statement.where(Job.tool_id == tool)
            return list(session.scalars(statement))

    def transition(
        self,
        job_id: str,
        target: JobStatus | str,
        *,
        message: str = "",
        error_code: str | None = None,
        error_message: str | None = None,
        result_ref: str | None = None,
    ) -> Job:
        with self.database.session() as session, session.begin():
            job = self._require_job(session, job_id)
            _current, target_status = require_transition(job.status, target)
            now = utcnow()
            job.status = target_status.value
            job.row_version += 1
            if target_status == JobStatus.RUNNING and job.started_at is None:
                job.started_at = now
            if target_status == JobStatus.QUEUED:
                job.queued_at = now
                job.lease_owner = None
                job.lease_expires_at = None
                job.heartbeat_at = None
                job.error_code = None
                job.error_message = None
                job.cancel_requested = False
            if target_status in {
                JobStatus.WAITING_PROVIDER,
                JobStatus.WAITING_RATE_LIMIT,
                JobStatus.AWAITING_APPROVAL,
            }:
                job.lease_owner = None
                job.lease_expires_at = None
                job.heartbeat_at = None
            if target_status in {JobStatus.COMPLETED, JobStatus.CANCELLED}:
                job.finished_at = now
                job.lease_owner = None
                job.lease_expires_at = None
                job.progress = 100 if target_status == JobStatus.COMPLETED else job.progress
            if target_status in {JobStatus.FAILED, JobStatus.PARTIAL, JobStatus.INTERRUPTED}:
                job.finished_at = now
                job.lease_owner = None
                job.lease_expires_at = None
            if target_status == JobStatus.CANCELLING:
                job.cancel_requested = True
            if result_ref is not None:
                job.result_ref = result_ref
            job.error_code = error_code
            job.error_message = error_message
            job.stage = target_status.value
            self._append_event(session, job, "state", message or f"Job {target_status.value}.")
            return job

    def start_external(self, job_id: str, worker_id: str) -> Job:
        with self.database.session() as session, session.begin():
            job = self._require_job(session, job_id)
            require_transition(job.status, JobStatus.RUNNING)
            now = utcnow()
            job.status = JobStatus.RUNNING.value
            job.stage = "running"
            job.started_at = job.started_at or now
            job.lease_owner = worker_id
            job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            job.heartbeat_at = now
            job.row_version += 1
            self._append_event(session, job, "state", f"Job started by {worker_id}.")
            return job

    def progress(
        self,
        job_id: str,
        progress: int,
        *,
        stage: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> Job:
        if not 0 <= progress <= 100:
            raise ValueError("Job progress must be between 0 and 100.")
        with self.database.session() as session, session.begin():
            job = self._require_job(session, job_id)
            if JobStatus(job.status) not in ACTIVE_STATUSES:
                raise JobConflict("Cannot update progress for an inactive job.")
            job.progress = progress
            job.stage = stage
            job.row_version += 1
            self._append_event(session, job, "progress", message, stage=stage, progress=progress, payload=payload)
            return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        status = JobStatus(job.status)
        if status in {JobStatus.QUEUED, JobStatus.WAITING_PROVIDER, JobStatus.WAITING_RATE_LIMIT, JobStatus.AWAITING_APPROVAL, JobStatus.INTERRUPTED}:
            return self.transition(job_id, JobStatus.CANCELLED, message="Job cancelled.")
        if status == JobStatus.RUNNING:
            return self.transition(job_id, JobStatus.CANCELLING, message="Cancellation requested.")
        if status in {JobStatus.CANCELLING, JobStatus.CANCELLED}:
            return job
        raise JobConflict(f"Job in {status.value} cannot be cancelled.")

    def retry(self, job_id: str) -> Job:
        with self.database.session() as session, session.begin():
            job = self._require_job(session, job_id)
            status = JobStatus(job.status)
            if status not in {JobStatus.FAILED, JobStatus.PARTIAL, JobStatus.INTERRUPTED}:
                raise JobConflict(f"Job in {status.value} cannot be retried.")
            if job.attempt >= job.max_attempts:
                raise JobConflict("Job retry limit has been reached.")
            competing = session.scalar(select(Job.id).where(
                Job.id != job.id,
                Job.dedupe_key == job.dedupe_key,
                Job.status.in_([active.value for active in ACTIVE_STATUSES]),
            ))
            if competing is not None:
                raise JobConflict(f"Equivalent work is already active as job {competing}.")
            require_transition(status, JobStatus.QUEUED)
            now = utcnow()
            job.status = JobStatus.QUEUED.value
            job.attempt += 1
            job.queued_at = now
            job.finished_at = None
            job.error_code = None
            job.error_message = None
            job.cancel_requested = False
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.stage = "queued"
            job.row_version += 1
            self._append_event(session, job, "state", "Job queued for retry.")
            return job

    def claim_next(self, worker_id: str) -> Job | None:
        for _attempt in range(5):
            with self.database.session() as session, session.begin():
                candidate_id = session.scalar(
                    select(Job.id)
                    .where(Job.status == JobStatus.QUEUED.value)
                    .order_by(Job.priority.desc(), Job.created_at)
                    .limit(1)
                )
                if candidate_id is None:
                    return None
                now = utcnow()
                result = session.execute(
                    update(Job)
                    .where(Job.id == candidate_id, Job.status == JobStatus.QUEUED.value)
                    .values(
                        status=JobStatus.RUNNING.value,
                        stage="running",
                        started_at=func.coalesce(Job.started_at, now),
                        lease_owner=worker_id,
                        lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                        heartbeat_at=now,
                        row_version=Job.row_version + 1,
                    )
                )
                if result.rowcount != 1:
                    continue
                job = self._require_job(session, candidate_id)
                self._append_event(session, job, "state", f"Job claimed by {worker_id}.")
                return job
        return None

    def heartbeat(self, job_id: str, worker_id: str) -> bool:
        with self.database.session() as session, session.begin():
            now = utcnow()
            result = session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == JobStatus.RUNNING.value,
                    Job.lease_owner == worker_id,
                )
                .values(
                    heartbeat_at=now,
                    lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                    row_version=Job.row_version + 1,
                )
            )
            return result.rowcount == 1

    def recover_expired(self, *, now: datetime | None = None) -> list[str]:
        now = now or utcnow()
        recovered: list[str] = []
        with self.database.session() as session, session.begin():
            jobs = list(session.scalars(
                select(Job).where(
                    Job.status == JobStatus.RUNNING.value,
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at < now,
                )
            ))
            for job in jobs:
                require_transition(JobStatus.RUNNING, JobStatus.INTERRUPTED)
                job.status = JobStatus.INTERRUPTED.value
                job.stage = JobStatus.INTERRUPTED.value
                job.finished_at = now
                job.error_code = "engine_crashed"
                job.error_message = "Worker lease expired before completion."
                job.lease_owner = None
                job.lease_expires_at = None
                job.row_version += 1
                self._append_event(session, job, "state", "Worker lease expired; job interrupted.")
                recovered.append(job.id)
        return recovered

    def events(self, job_id: str, *, after_event_id: int = 0, limit: int = 500) -> list[JobEvent]:
        with self.database.session() as session:
            if session.get(Job, job_id) is None:
                raise JobNotFound(job_id)
            return list(session.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job_id, JobEvent.event_id > after_event_id)
                .order_by(JobEvent.event_id)
                .limit(max(1, min(limit, 1000)))
            ))

    @staticmethod
    def _find_existing(
        session: Session,
        client_request_id: str | None,
        dedupe_key: str,
        active_values: list[str],
    ) -> Job | None:
        if client_request_id:
            existing = session.scalar(select(Job).where(Job.client_request_id == client_request_id))
            if existing is not None:
                return existing
        return session.scalar(
            select(Job)
            .where(Job.dedupe_key == dedupe_key, Job.status.in_(active_values))
            .order_by(Job.created_at)
        )

    @staticmethod
    def _require_job(session: Session, job_id: str) -> Job:
        job = session.get(Job, job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    @staticmethod
    def _attach_consumer(session: Session, job_id: str, consumer_type: str, consumer_id: str) -> None:
        existing = session.scalar(select(JobConsumer).where(
            JobConsumer.job_id == job_id,
            JobConsumer.consumer_type == consumer_type,
            JobConsumer.consumer_id == consumer_id,
        ))
        if existing is None:
            session.add(JobConsumer(
                job_id=job_id,
                consumer_type=consumer_type,
                consumer_id=consumer_id,
                requested_at=utcnow(),
            ))

    @staticmethod
    def _append_event(
        session: Session,
        job: Job,
        event_type: str,
        message: str,
        *,
        stage: str | None = None,
        progress: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> JobEvent:
        sequence = session.scalar(
            select(func.coalesce(func.max(JobEvent.job_sequence), 0)).where(JobEvent.job_id == job.id)
        ) + 1
        event = JobEvent(
            job_id=job.id,
            job_sequence=sequence,
            event_type=event_type,
            stage=stage or job.stage,
            progress=job.progress if progress is None else progress,
            message=message[:512],
            payload_json=canonical_json(payload or {}),
            created_at=utcnow(),
        )
        session.add(event)
        session.flush()
        return event
