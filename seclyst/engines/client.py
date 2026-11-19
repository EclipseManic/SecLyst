from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import uuid
from typing import Any


class EngineControlClient:
    """Best-effort authenticated reporter used only when an engine runs in SecLyst."""

    def __init__(self, tool: str) -> None:
        self.tool = tool
        self.base_url = os.getenv("SECLYST_CONTROL_URL", "").rstrip("/")
        self.token = os.getenv("SECLYST_ENGINE_TOKEN", "")
        self.enabled = bool(self.base_url and self.token and os.getenv("SECLYST_DURABLE_JOBS", "").lower() in {"1", "true", "yes", "on"})
        self._heartbeats: dict[str, tuple[threading.Event, threading.Thread]] = {}
        self._lock = threading.Lock()

    def register(
        self,
        operation: str,
        *,
        requested_job_id: str | None = None,
        inputs: list[dict[str, Any]] | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str | None, bool]:
        if not self.enabled:
            return None, True
        payload = {
            "tool": self.tool,
            "operation": operation,
            "requested_job_id": requested_job_id,
            "inputs": inputs or [],
            "parameters": {**(parameters or {}), "engine_request_id": str(uuid.uuid4())},
            "client_request_id": str(uuid.uuid4()),
        }
        response = self._request("/internal/v1/jobs/register", payload)
        if not response:
            return None, True
        job_id = response.get("job_id")
        should_execute = bool(response.get("should_execute", True))
        if job_id and should_execute:
            self._start_heartbeat(job_id)
        return job_id, should_execute

    def progress(
        self,
        job_id: str,
        progress: int,
        stage: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        return bool(self._request(f"/internal/v1/jobs/{job_id}/progress", {
            "tool": self.tool,
            "progress": max(0, min(progress, 100)),
            "stage": stage,
            "message": message,
            "payload": payload or {},
        }))

    def complete(self, job_id: str, *, result_ref: str | None = None, message: str = "Job completed.") -> bool:
        self._stop_heartbeat(job_id)
        if not self.enabled:
            return False
        return bool(self._request(f"/internal/v1/jobs/{job_id}/complete", {
            "tool": self.tool,
            "result_ref": result_ref,
            "message": message,
        }))

    def fail(self, job_id: str, code: str, message: str) -> bool:
        self._stop_heartbeat(job_id)
        if not self.enabled:
            return False
        return bool(self._request(f"/internal/v1/jobs/{job_id}/fail", {
            "tool": self.tool,
            "code": code,
            "message": message[:1000],
        }))

    def cancel(self, job_id: str) -> bool:
        self._stop_heartbeat(job_id)
        if not self.enabled:
            return False
        return bool(self._request(f"/internal/v1/jobs/{job_id}/cancelled", {"tool": self.tool}))

    def _start_heartbeat(self, job_id: str) -> None:
        stop = threading.Event()
        thread = threading.Thread(target=self._heartbeat_loop, args=(job_id, stop), daemon=True)
        with self._lock:
            self._heartbeats[job_id] = (stop, thread)
        thread.start()

    def _stop_heartbeat(self, job_id: str) -> None:
        with self._lock:
            state = self._heartbeats.pop(job_id, None)
        if state:
            state[0].set()
            if state[1] is not threading.current_thread():
                state[1].join(timeout=1)

    def _heartbeat_loop(self, job_id: str, stop: threading.Event) -> None:
        while not stop.wait(10):
            if not self._request(f"/internal/v1/jobs/{job_id}/heartbeat", {"tool": self.tool}):
                return

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-SecLyst-Engine-Token": self.token,
                "User-Agent": f"SecLyst-{self.tool}-engine",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError):
            return None
