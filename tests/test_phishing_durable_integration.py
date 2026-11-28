from __future__ import annotations

import threading
import time

import httpx
from uvicorn import Config, Server

from seclyst_backend.app import create_app
from seclyst_backend.database.session import Database
from seclyst_backend.jobs.service import JobService
from seclyst_backend.server import Supervisor


SAMPLE_EMAIL = b"""From: Security Team <security@example.com>
To: analyst@example.net
Subject: Account review
Date: Wed, 19 Nov 2026 10:00:00 +0000
Message-ID: <durable-test@example.com>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Please review the attached account notice.
"""


def test_phishing_analysis_publishes_durable_job(tmp_path, monkeypatch) -> None:
    shell_port = 7920
    ports = {
        "SECLYST_MALWARE_PORT": "7921",
        "SECLYST_IOC_PORT": "7922",
        "SECLYST_EVENTS_PORT": "7923",
        "SECLYST_PHISHING_PORT": "7924",
        "SECLYST_RULEFORGE_PORT": "7925",
    }
    for name, value in ports.items():
        monkeypatch.setenv(name, value)

    web_root = tmp_path / "web"
    web_root.mkdir()
    (web_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
    database = Database(tmp_path / "platform.db", create_schema=True)
    jobs = JobService(database, lease_seconds=10)
    supervisor = Supervisor(shell_port, durable_jobs_enabled=True)
    supervisor.start_all()
    app = create_app(
        supervisor=supervisor,
        job_service=jobs,
        durable_jobs_enabled=True,
        web_root=web_root,
        engine_tokens=supervisor.engine_tokens,
    )
    server = Server(Config(app=app, host="127.0.0.1", port=shell_port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = supervisor.status()
            if all(row["status"] == "online" for row in status["tools"].values()):
                break
            time.sleep(0.2)
        else:
            raise AssertionError(f"Engines did not start: {status}")

        with httpx.Client(timeout=15) as client:
            submitted = client.post(
                "http://127.0.0.1:7924/api/analyze",
                files={"email_file": ("sample.eml", SAMPLE_EMAIL, "message/rfc822")},
                data={"external_enrichment": "false", "resolve_redirects": "false"},
                headers={"X-Requested-With": "XMLHttpRequest", "X-SecLyst-Access": supervisor.browser_access_token},
            )
            submitted.raise_for_status()
            payload = submitted.json()
            job_id = payload["platform_job_id"]
            assert payload["task_id"] == job_id

            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                job = client.get(f"http://127.0.0.1:{shell_port}/api/v1/jobs/{job_id}").json()
                if job["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.2)
            assert job["status"] == "completed", job
            assert job["result_ref"].startswith("engine://phishing/scans/")

            events = client.get(
                f"http://127.0.0.1:{shell_port}/api/v1/jobs/{job_id}/events",
                params={"follow": "false"},
            ).text
            assert "event: progress" in events
            assert "Phishing analysis completed" in events
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        supervisor.stop_all()
        database.dispose()
