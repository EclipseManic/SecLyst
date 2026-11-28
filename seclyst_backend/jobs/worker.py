from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from ..database.models import Job
from .queue import JobQueue
from .service import JobService
from .states import JobStatus


@dataclass(frozen=True)
class JobResult:
    result_ref: str | None = None
    message: str = "Job completed."


JobHandler = Callable[[Job, JobService], JobResult]


class JobWorker:
    """Executes one claimed job at a time with a renewable worker lease."""

    def __init__(self, service: JobService, worker_id: str) -> None:
        self.service = service
        self.queue = JobQueue(service, worker_id)
        self.worker_id = worker_id
        self.handlers: dict[tuple[str, str], JobHandler] = {}

    def register(self, tool: str, operation: str, handler: JobHandler) -> None:
        self.handlers[(tool, operation)] = handler

    def run_once(self) -> Job | None:
        job = self.queue.claim()
        if job is None:
            return None
        handler = self.handlers.get((job.tool_id, job.operation))
        if handler is None:
            return self.service.transition(
                job.id,
                JobStatus.FAILED,
                message="No worker handles this operation.",
                error_code="unsupported_operation",
                error_message=f"No handler for {job.tool_id}.{job.operation}.",
            )

        stop = threading.Event()
        heartbeat = threading.Thread(target=self._heartbeat_loop, args=(job.id, stop), daemon=True)
        heartbeat.start()
        try:
            result = handler(job, self.service)
            current = self.service.get(job.id)
            if current.status == JobStatus.CANCELLING.value:
                return self.service.transition(job.id, JobStatus.CANCELLED, message="Job cancelled by worker.")
            return self.service.transition(
                job.id,
                JobStatus.COMPLETED,
                message=result.message,
                result_ref=result.result_ref,
            )
        except Exception as exc:  # Worker boundary converts exceptions into durable failures.
            return self.service.transition(
                job.id,
                JobStatus.FAILED,
                message="Job handler failed.",
                error_code="internal_error",
                error_message=str(exc)[:1000],
            )
        finally:
            stop.set()
            heartbeat.join(timeout=2)

    def _heartbeat_loop(self, job_id: str, stop: threading.Event) -> None:
        interval = max(1.0, self.service.lease_seconds / 3)
        while not stop.wait(interval):
            if not self.queue.heartbeat(job_id):
                return
