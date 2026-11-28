from seclyst_backend.database.session import Database
from seclyst_backend.jobs.service import JobCreate, JobService
from seclyst_backend.jobs.states import JobStatus
from seclyst_backend.jobs.worker import JobResult, JobWorker


def test_worker_completes_registered_handler(tmp_path) -> None:
    database = Database(tmp_path / "worker.db", create_schema=True)
    try:
        service = JobService(database, lease_seconds=5)
        job = service.create(JobCreate(tool="ruleforge", operation="render", inputs=[])).job
        worker = JobWorker(service, "worker-1")
        worker.register("ruleforge", "render", lambda _job, _service: JobResult("result://rendered"))
        completed = worker.run_once()
        assert completed and completed.id == job.id
        assert completed.status == JobStatus.COMPLETED.value
        assert completed.result_ref == "result://rendered"
    finally:
        database.dispose()


def test_worker_persists_handler_failure(tmp_path) -> None:
    database = Database(tmp_path / "worker-failure.db", create_schema=True)
    try:
        service = JobService(database)
        job = service.create(JobCreate(tool="events", operation="ingest", inputs=[])).job
        worker = JobWorker(service, "worker-1")

        def fail(_job, _service):
            raise RuntimeError("controlled failure")

        worker.register("events", "ingest", fail)
        failed = worker.run_once()
        assert failed and failed.id == job.id
        assert failed.status == JobStatus.FAILED.value
        assert failed.error_code == "internal_error"
        assert failed.error_message == "controlled failure"
    finally:
        database.dispose()


def test_worker_rejects_unregistered_operation(tmp_path) -> None:
    database = Database(tmp_path / "worker-unsupported.db", create_schema=True)
    try:
        service = JobService(database)
        service.create(JobCreate(tool="ioc", operation="unknown", inputs=[]))
        failed = JobWorker(service, "worker-1").run_once()
        assert failed and failed.status == JobStatus.FAILED.value
        assert failed.error_code == "unsupported_operation"
    finally:
        database.dispose()
