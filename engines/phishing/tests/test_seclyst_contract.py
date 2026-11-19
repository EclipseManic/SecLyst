import io

from run import app


def test_seclyst_health_contract() -> None:
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"engine": "phishing", "status": "ok"}


def test_analysis_reports_durable_platform_job(monkeypatch) -> None:
    import run as web_app

    calls = []

    class FakeControl:
        enabled = True

        def register(self, operation, **kwargs):
            calls.append(("register", operation, kwargs))
            return "platform-phishing-job", True

        def progress(self, job_id, progress, stage, message, payload):
            calls.append(("progress", job_id, progress, stage, message, payload))
            return True

        def complete(self, job_id, **kwargs):
            calls.append(("complete", job_id, kwargs))
            return True

        def fail(self, job_id, code, message):
            calls.append(("fail", job_id, code, message))
            return True

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            self.target(*self.args)

    def fake_analysis(task_id, _path, original_name, _external, _redirects):
        web_app._update_step(task_id, "parse", "in_progress")
        web_app._update_step(task_id, "parse", "done")
        web_app._set_result(
            task_id,
            {"file": {"name": original_name}, "verdict": "SAFE"},
            result_ref="engine://phishing/scans/history-1",
        )

    monkeypatch.setattr(web_app, "_control", FakeControl())
    monkeypatch.setattr(web_app.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(web_app, "_run_analysis", fake_analysis)
    with web_app._platform_job_lock:
        web_app._platform_job_ids.clear()

    response = web_app.app.test_client().post(
        "/api/analyze",
        data={"email_file": (io.BytesIO(b"From: analyst@example.com\n\nHello"), "sample.eml")},
        headers={"X-Requested-With": "XMLHttpRequest"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 202
    assert response.get_json()["task_id"] == "platform-phishing-job"
    assert response.get_json()["platform_job_id"] == "platform-phishing-job"
    assert any(call[0] == "progress" for call in calls)
    assert any(call[0] == "complete" for call in calls)
    assert not any(call[0] == "fail" for call in calls)


def test_missing_local_task_reports_platform_interruption(monkeypatch) -> None:
    import run as web_app

    class InterruptedControl:
        enabled = True

        @staticmethod
        def status(_job_id):
            return {
                "status": "interrupted",
                "progress": 47,
                "stage": "attachments",
                "error_message": "Worker lease expired before completion.",
            }

    monkeypatch.setattr(web_app, "_control", InterruptedControl())
    with web_app._tasks_lock:
        web_app._tasks.pop("interrupted-job", None)
    response = web_app.app.test_client().get("/api/analyze/interrupted-job/progress")
    assert response.status_code == 200
    assert response.get_json()["status"] == "error"
    assert response.get_json()["progress_pct"] == 47
    assert response.get_json()["error"] == "Worker lease expired before completion."
