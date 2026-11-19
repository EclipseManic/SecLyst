from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ..jobs.service import JobConflict, JobCreate, JobInputValue, JobNotFound, JobService
from ..jobs.states import InvalidTransition, JobStatus


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)


class EngineInput(BaseModel):
    type: str = Field(min_length=1, max_length=32)
    ref: str = Field(min_length=1, max_length=1024)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EngineRegister(BaseModel):
    tool: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    operation: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    requested_job_id: str | None = None
    inputs: list[EngineInput] = Field(default_factory=list, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    client_request_id: str | None = Field(default=None, max_length=128)


class EngineProgress(BaseModel):
    tool: str
    progress: int = Field(ge=0, le=100)
    stage: str = Field(min_length=1, max_length=96)
    message: str = Field(default="", max_length=512)
    payload: dict[str, Any] = Field(default_factory=dict)


class EngineCompletion(BaseModel):
    tool: str
    message: str = Field(default="Job completed.", max_length=512)
    result_ref: str | None = Field(default=None, max_length=512)


class EngineFailure(BaseModel):
    tool: str
    code: str = Field(min_length=1, max_length=96)
    message: str = Field(min_length=1, max_length=1000)


class EngineIdentity(BaseModel):
    tool: str


def service(request: Request) -> JobService:
    if not request.app.state.durable_jobs_enabled:
        raise HTTPException(status_code=503, detail={"code": "durable_jobs_disabled", "message": "Durable jobs are disabled."})
    return request.app.state.job_service


def authorize(request: Request, tool: str, token: str | None) -> None:
    expected = request.app.state.engine_tokens.get(tool)
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=403, detail={"code": "invalid_engine_token", "message": "Engine token is invalid."})


def translate_conflict(exc: Exception) -> HTTPException:
    if isinstance(exc, JobNotFound):
        return HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job not found."})
    return HTTPException(status_code=409, detail={"code": "job_conflict", "message": str(exc)})


@router.post("/jobs/register")
def register_job(
    body: EngineRegister,
    request: Request,
    engine_token: str | None = Header(default=None, alias="X-SecLyst-Engine-Token"),
) -> dict[str, Any]:
    authorize(request, body.tool, engine_token)
    jobs = service(request)
    worker_id = f"engine:{body.tool}"
    try:
        if body.requested_job_id:
            job = jobs.get(body.requested_job_id)
            if job.tool_id != body.tool:
                raise JobConflict("Requested job belongs to another tool.")
            started = jobs.start_external(job.id, worker_id)
            return {"job_id": started.id, "status": started.status, "should_execute": True}

        created = jobs.create(JobCreate(
            tool=body.tool,
            operation=body.operation,
            inputs=[
                JobInputValue(type=value.type, ref=value.ref, sha256=value.sha256, metadata=value.metadata)
                for value in body.inputs
            ],
            parameters=body.parameters,
            client_request_id=body.client_request_id,
            consumer_type="engine",
            consumer_id=body.tool,
        ))
        if created.deduplicated:
            return {"job_id": created.job.id, "status": created.job.status, "should_execute": False}
        started = jobs.start_external(created.job.id, worker_id)
        return {"job_id": started.id, "status": started.status, "should_execute": True}
    except (JobNotFound, JobConflict, InvalidTransition) as exc:
        raise translate_conflict(exc) from exc


@router.post("/jobs/{job_id}/progress")
def report_progress(
    job_id: str,
    body: EngineProgress,
    request: Request,
    engine_token: str | None = Header(default=None, alias="X-SecLyst-Engine-Token"),
) -> dict[str, Any]:
    authorize(request, body.tool, engine_token)
    jobs = service(request)
    try:
        job = jobs.get(job_id)
        if job.tool_id != body.tool:
            raise JobConflict("Job belongs to another tool.")
        if not jobs.heartbeat(job_id, f"engine:{body.tool}"):
            raise JobConflict("Engine no longer owns this job lease.")
        updated = jobs.progress(
            job_id,
            body.progress,
            stage=body.stage,
            message=body.message,
            payload=body.payload,
        )
        return {"job_id": updated.id, "status": updated.status, "progress": updated.progress}
    except (JobNotFound, JobConflict, InvalidTransition) as exc:
        raise translate_conflict(exc) from exc


@router.post("/jobs/{job_id}/heartbeat")
def heartbeat(
    job_id: str,
    body: EngineIdentity,
    request: Request,
    engine_token: str | None = Header(default=None, alias="X-SecLyst-Engine-Token"),
) -> dict[str, bool]:
    authorize(request, body.tool, engine_token)
    if not service(request).heartbeat(job_id, f"engine:{body.tool}"):
        raise HTTPException(status_code=409, detail={"code": "lease_lost", "message": "Engine no longer owns this job lease."})
    return {"ok": True}


@router.post("/jobs/{job_id}/complete")
def complete_job(
    job_id: str,
    body: EngineCompletion,
    request: Request,
    engine_token: str | None = Header(default=None, alias="X-SecLyst-Engine-Token"),
) -> dict[str, str]:
    authorize(request, body.tool, engine_token)
    jobs = service(request)
    try:
        job = jobs.get(job_id)
        if job.tool_id != body.tool:
            raise JobConflict("Job belongs to another tool.")
        target = JobStatus.CANCELLED if job.status == JobStatus.CANCELLING.value else JobStatus.COMPLETED
        completed = jobs.transition(job_id, target, message=body.message, result_ref=body.result_ref)
        return {"job_id": completed.id, "status": completed.status}
    except (JobNotFound, JobConflict, InvalidTransition) as exc:
        raise translate_conflict(exc) from exc


@router.post("/jobs/{job_id}/fail")
def fail_job(
    job_id: str,
    body: EngineFailure,
    request: Request,
    engine_token: str | None = Header(default=None, alias="X-SecLyst-Engine-Token"),
) -> dict[str, str]:
    authorize(request, body.tool, engine_token)
    jobs = service(request)
    try:
        job = jobs.get(job_id)
        if job.tool_id != body.tool:
            raise JobConflict("Job belongs to another tool.")
        failed = jobs.transition(
            job_id,
            JobStatus.FAILED,
            message="Engine reported a job failure.",
            error_code=body.code,
            error_message=body.message,
        )
        return {"job_id": failed.id, "status": failed.status}
    except (JobNotFound, JobConflict, InvalidTransition) as exc:
        raise translate_conflict(exc) from exc


@router.post("/jobs/{job_id}/cancelled")
def cancel_job(
    job_id: str,
    body: EngineIdentity,
    request: Request,
    engine_token: str | None = Header(default=None, alias="X-SecLyst-Engine-Token"),
) -> dict[str, str]:
    authorize(request, body.tool, engine_token)
    jobs = service(request)
    try:
        job = jobs.get(job_id)
        if job.tool_id != body.tool:
            raise JobConflict("Job belongs to another tool.")
        if job.status == JobStatus.RUNNING.value:
            jobs.cancel(job_id)
        cancelled = jobs.transition(job_id, JobStatus.CANCELLED, message="Engine confirmed cancellation.")
        return {"job_id": cancelled.id, "status": cancelled.status}
    except (JobNotFound, JobConflict, InvalidTransition) as exc:
        raise translate_conflict(exc) from exc
