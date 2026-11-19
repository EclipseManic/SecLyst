from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_PROVIDER = "waiting_provider"
    WAITING_RATE_LIMIT = "waiting_rate_limit"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLING = "cancelling"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


ACTIVE_STATUSES = frozenset({
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.WAITING_PROVIDER,
    JobStatus.WAITING_RATE_LIMIT,
    JobStatus.AWAITING_APPROVAL,
    JobStatus.CANCELLING,
})

TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.CANCELLED})

ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset({
        JobStatus.WAITING_PROVIDER,
        JobStatus.WAITING_RATE_LIMIT,
        JobStatus.AWAITING_APPROVAL,
        JobStatus.PARTIAL,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLING,
        JobStatus.INTERRUPTED,
    }),
    JobStatus.WAITING_PROVIDER: frozenset({JobStatus.QUEUED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.WAITING_RATE_LIMIT: frozenset({JobStatus.QUEUED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.AWAITING_APPROVAL: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.CANCELLING: frozenset({JobStatus.CANCELLED, JobStatus.FAILED}),
    JobStatus.INTERRUPTED: frozenset({JobStatus.QUEUED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.PARTIAL: frozenset({JobStatus.QUEUED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


class InvalidTransition(ValueError):
    pass


def require_transition(current: JobStatus | str, target: JobStatus | str) -> tuple[JobStatus, JobStatus]:
    current_status = JobStatus(current)
    target_status = JobStatus(target)
    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidTransition(f"Cannot transition job from {current_status.value} to {target_status.value}.")
    return current_status, target_status
