import io
from fastapi.testclient import TestClient
from seclyst.app import create_app
from seclyst.artifacts import ArtifactStore
from seclyst.database.session import Database
from seclyst.jobs.service import JobService


class Supervisor:
    tools = {}
    status = staticmethod(lambda: {"tools": {}})
    summary = staticmethod(lambda: {"collections": {}})


def test_email_to_detection_run_is_persisted(tmp_path):
    db = Database(tmp_path / "workflow.db", create_schema=True)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>")
    store = ArtifactStore(db, tmp_path / "objects")
    artifact, _ = store.ingest(
        io.BytesIO(b"From: a@example.com\n\nHello"), original_name="sample.eml", declared_type="message/rfc822"
    )
    app = create_app(
        supervisor=Supervisor(),
        job_service=JobService(db),
        durable_jobs_enabled=True,
        web_root=web,
        artifact_store=store,
    )
    api = TestClient(app)
    response = api.post("/api/v1/runs", json={"question": "Is this email malicious?", "artifact_id": artifact.id})
    assert response.status_code == 201
    run = response.json()
    assert len(run["plan"]) == 5
    assert run["initial_job_id"]
    detection = api.post(f"/api/v1/runs/{run['id']}/detections")
    assert detection.status_code == 201
    assert detection.json()["status"] == "draft"
    db.dispose()
