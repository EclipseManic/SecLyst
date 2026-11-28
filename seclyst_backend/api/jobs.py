from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from ..jobs.service import JobConflict, JobCreate, JobInputValue, JobNotFound, JobService
from ..jobs.states import ACTIVE_STATUSES, InvalidTransition, JobStatus
from .schemas import JobCreateResponse, JobCreateSchema, JobEventView, JobView


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def service_from_request(request: Request) -> JobService:
    if not request.app.state.durable_jobs_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "durable_jobs_disabled", "message": "Durable jobs are disabled."},
        )
    return request.app.state.job_service


def job_or_404(service: JobService, job_id: str):
    try:
        return service.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job not found."}) from exc


@router.post("", response_model=JobCreateResponse, status_code=202)
def create_job(body: JobCreateSchema, request: Request) -> JobCreateResponse:
    service = service_from_request(request)
    try:
        result = service.create(JobCreate(
            tool=body.tool,
            operation=body.operation,
            inputs=[
                JobInputValue(type=item.type, ref=item.ref, sha256=item.sha256, metadata=item.metadata)
                for item in body.inputs
            ],
            parameters=body.parameters,
            priority_class=body.priority_class,
            priority=body.priority,
            client_request_id=body.client_request_id,
            configuration_hash=body.configuration_hash,
            max_attempts=body.max_attempts,
            force_refresh=body.force_refresh,
        ))
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail={"code": "job_conflict", "message": str(exc)}) from exc
    return JobCreateResponse(
        id=result.job.id,
        status=result.job.status,
        deduplicated=result.deduplicated,
        attached_to_job_id=result.attached_to_job_id,
        created_at=result.job.created_at,
    )


@router.get("", response_model=list[JobView])
def list_jobs(
    request: Request,
    job_status: str | None = Query(default=None, alias="status"),
    tool: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[JobView]:
    service = service_from_request(request)
    try:
        return [JobView.from_job(job) for job in service.list(status=job_status, tool=tool, limit=limit)]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_status", "message": str(exc)}) from exc


@router.get("/{job_id}", response_model=JobView)
def get_job(job_id: str, request: Request) -> JobView:
    return JobView.from_job(job_or_404(service_from_request(request), job_id))


@router.post("/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str, request: Request) -> JobView:
    service = service_from_request(request)
    try:
        return JobView.from_job(service.cancel(job_id))
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job not found."}) from exc
    except (JobConflict, InvalidTransition) as exc:
        raise HTTPException(status_code=409, detail={"code": "job_conflict", "message": str(exc)}) from exc


@router.post("/{job_id}/retry", response_model=JobView)
def retry_job(job_id: str, request: Request) -> JobView:
    service = service_from_request(request)
    try:
        return JobView.from_job(service.retry(job_id))
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job not found."}) from exc
    except (JobConflict, InvalidTransition) as exc:
        raise HTTPException(status_code=409, detail={"code": "job_conflict", "message": str(exc)}) from exc


@router.get("/{job_id}/result")
def get_job_result(job_id: str, request: Request) -> dict[str, str]:
    job = job_or_404(service_from_request(request), job_id)
    if not job.result_ref:
        raise HTTPException(status_code=409, detail={"code": "result_unavailable", "message": "Job result is not available."})
    return {"job_id": job.id, "result_ref": job.result_ref}


@router.get("/{job_id}/events")
async def job_events(
    job_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after: int = Query(default=0, ge=0),
    follow: bool = True,
) -> StreamingResponse:
    service = service_from_request(request)
    job_or_404(service, job_id)
    cursor = max(after, int(last_event_id or 0))

    async def stream() -> AsyncIterator[str]:
        nonlocal cursor
        last_ping = time.monotonic()
        while True:
            events = service.events(job_id, after_event_id=cursor)
            for event in events:
                cursor = event.event_id
                view = JobEventView.from_event(event)
                data = json.dumps(view.model_dump(mode="json"), separators=(",", ":"))
                yield f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data}\n\n"
            if not follow:
                return
            job = service.get(job_id)
            if JobStatus(job.status) not in ACTIVE_STATUSES and not events:
                return
            if await request.is_disconnected():
                return
            if time.monotonic() - last_ping >= 15:
                yield ": heartbeat\n\n"
                last_ping = time.monotonic()
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
