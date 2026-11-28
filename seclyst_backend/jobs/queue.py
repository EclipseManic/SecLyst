from __future__ import annotations

from .service import JobService


class JobQueue:
    """Lease-based queue facade kept separate from job lifecycle operations."""

    def __init__(self, service: JobService, worker_id: str) -> None:
        self.service = service
        self.worker_id = worker_id

    def claim(self):
        return self.service.claim_next(self.worker_id)

    def heartbeat(self, job_id: str) -> bool:
        return self.service.heartbeat(job_id, self.worker_id)
