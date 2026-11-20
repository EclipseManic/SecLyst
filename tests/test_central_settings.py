from fastapi.testclient import TestClient
from seclyst.app import create_app
from seclyst.database.session import Database
from seclyst.jobs.service import JobService


class Supervisor:
    tools = {}
    status = staticmethod(lambda: {"tools": {}})
    summary = staticmethod(lambda: {"collections": {}})


def test_tool_settings_are_central_and_persistent(tmp_path):
    db = Database(tmp_path / "db.sqlite", create_schema=True)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>")
    app = create_app(
        supervisor=Supervisor(),
        job_service=JobService(db),
        durable_jobs_enabled=True,
        web_root=web,
        runtime_dir=tmp_path / "runtime",
    )
    api = TestClient(app)
    saved = api.put("/api/v1/settings/tools/events", json={"values": {"page_limit": 500}})
    assert saved.status_code == 200 and saved.json()["restart_required"] is True
    settings = api.get("/api/v1/settings").json()
    assert settings["tools"]["events"]["page_limit"] == 500
    assert "virustotal" in settings["providers"]
    db.dispose()
