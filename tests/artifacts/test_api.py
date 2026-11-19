from fastapi.testclient import TestClient

from seclyst.app import create_app
from seclyst.artifacts import ArtifactStore
from seclyst.database.session import Database
from seclyst.jobs.service import JobService


class Supervisor:
    tools = {}

    @staticmethod
    def status(): return {"tools": {}}

    @staticmethod
    def summary(): return {"collections": {}}


def test_artifact_upload_metadata_download_and_delete(tmp_path) -> None:
    database = Database(tmp_path / "api.db", create_schema=True)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(
        supervisor=Supervisor(),
        job_service=JobService(database),
        durable_jobs_enabled=True,
        web_root=web,
        artifact_store=ArtifactStore(database, tmp_path / "objects"),
    )
    api = TestClient(app)
    try:
        uploaded = api.post("/api/v1/artifacts", files={"file": ("sample.bin", b"artifact bytes", "application/octet-stream")})
        assert uploaded.status_code == 201
        artifact = uploaded.json()
        assert artifact["deduplicated"] is False
        assert api.get(f"/api/v1/artifacts/{artifact['id']}").json()["sha256"] == artifact["sha256"]
        download = api.get(f"/api/v1/artifacts/{artifact['id']}/download")
        assert download.content == b"artifact bytes"
        assert download.headers["content-disposition"].startswith("attachment")
        assert api.delete(f"/api/v1/artifacts/{artifact['id']}").status_code == 204
        assert api.get(f"/api/v1/artifacts/{artifact['id']}").status_code == 404
    finally:
        database.dispose()
