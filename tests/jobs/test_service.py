from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from seclyst.database.models import JobConsumer, JobEvent
from seclyst.database.session import Database
from seclyst.jobs.service import JobConflict, JobCreate, JobInputValue, JobService, utcnow
from seclyst.jobs.states import JobStatus


@pytest.fixture
def service(tmp_path) -> JobService:
    database = Database(tmp_path / "jobs.db", create_schema=True)
    service = JobService(database, lease_seconds=10)
    yield service
    database.dispose()


def command(*, consumer: str = "consumer-a", client_request_id: str | None = None) -> JobCreate:
    return JobCreate(
        tool="malware",
        operation="scan",
        inputs=[JobInputValue(type="artifact", ref="artifact-1", sha256="a" * 64)],
        parameters={"offline": True},
        client_request_id=client_request_id,
        consumer_id=consumer,
    )


def test_create_is_idempotent_and_active_jobs_are_single_flight(service: JobService) -> None:
    first = service.create(command(consumer="consumer-a", client_request_id="request-1"))
    repeated_request = service.create(command(consumer="consumer-b", client_request_id="request-1"))
    same_work = service.create(command(consumer="consumer-c"))

    assert first.deduplicated is False
    assert repeated_request.job.id == first.job.id
    assert same_work.job.id == first.job.id
    assert same_work.deduplicated is True

    with service.database.session() as session:
        count = session.scalar(select(func.count()).select_from(JobConsumer).where(JobConsumer.job_id == first.job.id))
    assert count == 3


def test_completed_work_can_be_submitted_as_a_new_job(service: JobService) -> None:
    first = service.create(command()).job
    claimed = service.claim_next("worker-1")
    assert claimed and claimed.id == first.id
    service.transition(first.id, JobStatus.COMPLETED, result_ref="result://one")

    second = service.create(command(consumer="consumer-b"))
    assert second.job.id != first.id
    assert second.deduplicated is False


def test_progress_events_are_ordered_and_replayable(service: JobService) -> None:
    job = service.create(command()).job
    service.claim_next("worker-1")
    service.progress(job.id, 25, stage="static", message="Static analysis started.")
    service.progress(job.id, 80, stage="providers", message="Provider lookups running.")
    service.transition(job.id, JobStatus.COMPLETED, result_ref="result://done")

    events = service.events(job.id)
    assert [event.job_sequence for event in events] == list(range(1, len(events) + 1))
    replay = service.events(job.id, after_event_id=events[1].event_id)
    assert replay[0].event_id == events[2].event_id
    assert replay[-1].event_type == "state"


def test_claim_heartbeat_and_expired_lease_recovery(service: JobService) -> None:
    job = service.create(command()).job
    claimed = service.claim_next("worker-1")
    assert claimed and claimed.lease_owner == "worker-1"
    assert service.claim_next("worker-2") is None
    assert service.heartbeat(job.id, "worker-2") is False
    assert service.heartbeat(job.id, "worker-1") is True

    with service.database.session() as session, session.begin():
        persisted = session.get(type(claimed), job.id)
        persisted.lease_expires_at = utcnow() - timedelta(seconds=1)

    assert service.recover_expired() == [job.id]
    recovered = service.get(job.id)
    assert recovered.status == JobStatus.INTERRUPTED.value
    assert recovered.error_code == "engine_crashed"


def test_retry_and_cancel_are_explicit_and_bounded(service: JobService) -> None:
    job = service.create(command()).job
    service.claim_next("worker-1")
    service.transition(job.id, JobStatus.FAILED, error_code="engine_crashed")
    retried = service.retry(job.id)
    assert retried.status == JobStatus.QUEUED.value
    assert retried.attempt == 1
    cancelled = service.cancel(job.id)
    assert cancelled.status == JobStatus.CANCELLED.value
    with pytest.raises(JobConflict):
        service.retry(job.id)


def test_retry_refuses_duplicate_active_work(service: JobService) -> None:
    original = service.create(command(consumer="original")).job
    service.claim_next("worker-1")
    service.transition(original.id, JobStatus.FAILED, error_code="engine_crashed")
    replacement = service.create(command(consumer="replacement")).job
    assert replacement.id != original.id
    with pytest.raises(JobConflict, match="already active"):
        service.retry(original.id)


def test_progress_rejects_inactive_jobs(service: JobService) -> None:
    job = service.create(command()).job
    service.cancel(job.id)
    with pytest.raises(JobConflict):
        service.progress(job.id, 10, stage="invalid")


def test_event_sequence_is_unique_per_job(service: JobService) -> None:
    first = service.create(command(consumer="one")).job
    second = service.create(JobCreate(tool="ioc", operation="lookup", inputs=[])).job
    with service.database.session() as session:
        events = list(session.scalars(select(JobEvent).order_by(JobEvent.event_id)))
    assert [(event.job_id, event.job_sequence) for event in events] == [(first.id, 1), (second.id, 1)]


def test_concurrent_identical_creators_share_one_job(service: JobService) -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(
            lambda index: service.create(command(consumer=f"consumer-{index}")),
            range(8),
        ))
    assert len({result.job.id for result in results}) == 1
    with service.database.session() as session:
        consumer_count = session.scalar(select(func.count()).select_from(JobConsumer))
    assert consumer_count == 8


def test_concurrent_workers_claim_each_job_once(service: JobService) -> None:
    for index in range(6):
        service.create(JobCreate(
            tool="ioc",
            operation="lookup",
            inputs=[JobInputValue(type="ioc", ref=f"192.0.2.{index}")],
        ))
    with ThreadPoolExecutor(max_workers=6) as executor:
        claimed = list(executor.map(lambda index: service.claim_next(f"worker-{index}"), range(6)))
    claimed_ids = [job.id for job in claimed if job is not None]
    assert len(claimed_ids) == len(set(claimed_ids)) == 6
    assert service.claim_next("worker-extra") is None
