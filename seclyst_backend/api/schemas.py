from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ..database.models import Job, JobEvent


class JobInputSchema(BaseModel):
    type: str = Field(min_length=1, max_length=32)
    ref: str = Field(min_length=1, max_length=1024)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobCreateSchema(BaseModel):
    tool: str = Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_-]*$")
    operation: str = Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_.-]*$")
    inputs: list[JobInputSchema] = Field(default_factory=list, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    priority_class: Literal["interactive", "workflow", "batch"] = "interactive"
    priority: int = Field(default=100, ge=0, le=1000)
    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)
    configuration_hash: str = Field(default="", max_length=64)
    max_attempts: int = Field(default=3, ge=0, le=20)
    force_refresh: bool = False

    @field_validator("configuration_hash")
    @classmethod
    def validate_configuration_hash(cls, value: str) -> str:
        if value and (len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value)):
            raise ValueError("configuration_hash must be an empty string or a SHA-256 hex digest")
        return value.lower()


class JobCreateResponse(BaseModel):
    id: str
    status: str
    deduplicated: bool
    attached_to_job_id: str | None
    created_at: datetime


class JobView(BaseModel):
    id: str
    tool: str
    operation: str
    status: str
    priority_class: str
    priority: int
    progress: int
    stage: str
    attempt: int
    max_attempts: int
    cancel_requested: bool
    result_ref: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: Job) -> "JobView":
        return cls(
            id=job.id,
            tool=job.tool_id,
            operation=job.operation,
            status=job.status,
            priority_class=job.priority_class,
            priority=job.priority,
            progress=job.progress,
            stage=job.stage,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            cancel_requested=job.cancel_requested,
            result_ref=job.result_ref,
            error_code=job.error_code,
            error_message=job.error_message,
            created_at=job.created_at,
            queued_at=job.queued_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class JobEventView(BaseModel):
    event_id: int
    job_id: str
    job_sequence: int
    event_type: str
    stage: str | None
    progress: int | None
    message: str
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_event(cls, event: JobEvent) -> "JobEventView":
        return cls(
            event_id=event.event_id,
            job_id=event.job_id,
            job_sequence=event.job_sequence,
            event_type=event.event_type,
            stage=event.stage,
            progress=event.progress,
            message=event.message,
            payload=json.loads(event.payload_json),
            created_at=event.created_at,
        )


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    correlation_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
