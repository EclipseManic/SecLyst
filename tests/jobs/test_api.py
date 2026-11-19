from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from seclyst.app import create_app
from seclyst.database.session import Database
from seclyst.jobs.service import JobService


@dataclass
class FakeTool:
    url: str


class FakeSupervisor:
    tools = {"malware": FakeTool("http://127.0.0.1:7101/")}

    @staticmethod
    def status():
        return {"product": "SecLyst", "tools": {}}

    @staticmethod
    def summary():
        return {"collections": {}}


def client(tmp_path, *, enabled: bool = True) -> tuple[TestClient, Database]:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>Seclyst test</title>", encoding="utf-8")
    database = Database(tmp_path / "api.db", create_schema=True)
    app = create_app(
        supervisor=FakeSupervisor(),
        job_service=JobService(database),
        durable_jobs_enabled=enabled,
        web_root=web,
    )
    return TestClient(app), database


def test_job_api_create_get_cancel_and_event_replay(tmp_path) -> None:
    api, database = client(tmp_path)
    try:
        created = api.post("/api/v1/jobs", json={
            "tool": "malware",
            "operation": "scan",
            "inputs": [{"type": "artifact", "ref": "artifact-1", "sha256": "a" * 64}],
            "client_request_id": "request-1",
        })
        assert created.status_code == 202
        job_id = created.json()["id"]
        assert api.get(f"/api/v1/jobs/{job_id}").json()["status"] == "queued"
        assert len(api.get("/api/v1/jobs").json()) == 1

        replay = api.get(f"/api/v1/jobs/{job_id}/events?follow=false")
        assert replay.status_code == 200
        assert "Job queued" in replay.text

        cancelled = api.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert api.get(f"/api/v1/jobs/{job_id}/result").status_code == 409
    finally:
        database.dispose()


def test_job_api_idempotency_and_error_envelope(tmp_path) -> None:
    api, database = client(tmp_path)
    try:
        body = {"tool": "ioc", "operation": "lookup", "client_request_id": "same-request"}
        first = api.post("/api/v1/jobs", json=body)
        second = api.post("/api/v1/jobs", json=body)
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["deduplicated"] is True
        missing = api.get("/api/v1/jobs/missing")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "job_not_found"
    finally:
        database.dispose()


def test_job_api_feature_flag(tmp_path) -> None:
    api, database = client(tmp_path, enabled=False)
    try:
        response = api.get("/api/v1/jobs")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "durable_jobs_disabled"
    finally:
        database.dispose()


def test_sse_replays_only_events_after_last_event_id(tmp_path) -> None:
    api, database = client(tmp_path)
    try:
        created = api.post("/api/v1/jobs", json={"tool": "events", "operation": "ingest"}).json()
        job_id = created["id"]
        service = api.app.state.job_service
        service.claim_next("worker-1")
        service.progress(job_id, 40, stage="parsing", message="Parsing events.")
        first_event = service.events(job_id)[0]

        replay = api.get(
            f"/api/v1/jobs/{job_id}/events?follow=false",
            headers={"Last-Event-ID": str(first_event.event_id)},
        )
        assert replay.status_code == 200
        assert "Job queued" not in replay.text
        assert "Job claimed" in replay.text
        assert "Parsing events" in replay.text
    finally:
        database.dispose()


def test_fastapi_shell_fallback_and_security_headers(tmp_path) -> None:
    api, database = client(tmp_path)
    try:
        shell = api.get("/not-a-file")
        assert shell.status_code == 200
        assert "<title>Seclyst test" in shell.text
        assert shell.headers["X-Frame-Options"] == "DENY"
        assert "frame-src http://127.0.0.1:7101" in shell.headers["Content-Security-Policy"]
        traversal = api.get("/%2e%2e/README.md")
        assert traversal.status_code == 403
        assert traversal.json()["error"]["code"] == "forbidden_path"
    finally:
        database.dispose()
