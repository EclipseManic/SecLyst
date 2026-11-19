from __future__ import annotations

from .service import JobService


def recover_interrupted_jobs(service: JobService) -> list[str]:
    """Mark jobs with expired worker leases explicitly interrupted."""
    return service.recover_expired()
