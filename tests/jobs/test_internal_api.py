from fastapi.testclient import TestClient

from seclyst.app import create_app
from seclyst.database.session import Database
from seclyst.jobs.service import JobService


class FakeSupervisor:
    tools = {}

    @staticmethod
    def status():
        return {"tools": {}}

    @staticmethod
    def summary():
        return {"collections": {}}


def make_client(tmp_path) -> tuple[TestClient, Database]:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    database = Database(tmp_path / "internal.db", create_schema=True)
    app = create_app(
        supervisor=FakeSupervisor(),
        job_service=JobService(database),
        durable_jobs_enabled=True,
        web_root=web,
        engine_tokens={"malware": "malware-token", "phishing": "phishing-token"},
    )
    return TestClient(app), database


def test_engine_register_progress_and_complete(tmp_path) -> None:
    api, database = make_client(tmp_path)
    headers = {"X-SecLyst-Engine-Token": "malware-token"}
    try:
        registration = api.post("/internal/v1/jobs/register", headers=headers, json={
            "tool": "malware",
            "operation": "scan",
            "inputs": [{"type": "artifact", "ref": "sha256:a", "sha256": "a" * 64}],
            "parameters": {"engine_request_id": "request-1"},
        })
        assert registration.status_code == 200
        job_id = registration.json()["job_id"]
        assert registration.json()["should_execute"] is True

        progress = api.post(f"/internal/v1/jobs/{job_id}/progress", headers=headers, json={
            "tool": "malware",
            "progress": 35,
            "stage": "offline",
            "message": "Static analysis running.",
            "payload": {"filename": "sample.bin"},
        })
        assert progress.status_code == 200
        assert progress.json()["progress"] == 35

        completed = api.post(f"/internal/v1/jobs/{job_id}/complete", headers=headers, json={
            "tool": "malware",
            "message": "Scan completed.",
            "result_ref": f"engine://malware/scans/{job_id}",
        })
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert api.get(f"/api/v1/jobs/{job_id}").json()["result_ref"].endswith(job_id)
    finally:
        database.dispose()


def test_engine_token_and_tool_identity_are_enforced(tmp_path) -> None:
    api, database = make_client(tmp_path)
    try:
        body = {"tool": "malware", "operation": "scan"}
        assert api.post("/internal/v1/jobs/register", json=body).status_code == 403
        assert api.post(
            "/internal/v1/jobs/register",
            headers={"X-SecLyst-Engine-Token": "phishing-token"},
            json=body,
        ).status_code == 403
    finally:
        database.dispose()


def test_engine_can_adopt_an_orchestrated_job(tmp_path) -> None:
    api, database = make_client(tmp_path)
    try:
        created = api.post("/api/v1/jobs", json={"tool": "phishing", "operation": "analyze"}).json()
        adopted = api.post(
            "/internal/v1/jobs/register",
            headers={"X-SecLyst-Engine-Token": "phishing-token"},
            json={
                "tool": "phishing",
                "operation": "analyze",
                "requested_job_id": created["id"],
            },
        )
        assert adopted.status_code == 200
        assert adopted.json() == {"job_id": created["id"], "status": "running", "should_execute": True}
    finally:
        database.dispose()
