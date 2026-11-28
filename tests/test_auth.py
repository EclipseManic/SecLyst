from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from seclyst_backend.app import create_app
from seclyst_backend.auth import AuthService, PasswordStore, SessionManager
from seclyst_backend.database.session import Database
from seclyst_backend.jobs.service import JobService

PASSWORD = "correct-horse-battery-staple"


class Supervisor:
    tools: dict = {}
    status = staticmethod(lambda: {"tools": {}})
    summary = staticmethod(lambda: {"collections": {}})


def make_client(tmp_path, *, auth: AuthService | None) -> TestClient:
    db = Database(tmp_path / "db.sqlite", create_schema=True)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(
        supervisor=Supervisor(),
        job_service=JobService(db),
        durable_jobs_enabled=True,
        web_root=web,
        data_dir=tmp_path / "data",
        auth=auth,
    )
    return TestClient(app)


def test_password_store_hashes_and_verifies(tmp_path) -> None:
    store = PasswordStore(tmp_path)
    assert store.configured() is False
    store.set(PASSWORD)
    assert store.configured() is True
    assert store.verify(PASSWORD) is True
    assert store.verify("wrong-password-here") is False
    # The plaintext must never be written to disk.
    assert PASSWORD not in store.path.read_text(encoding="utf-8")


def test_password_store_rejects_short_passwords(tmp_path) -> None:
    store = PasswordStore(tmp_path)
    with pytest.raises(ValueError):
        store.set("short")


def test_session_manager_issues_expires_and_revokes() -> None:
    sessions = SessionManager(ttl_seconds=60)
    sid = sessions.create()
    assert sessions.valid(sid) is True
    sessions.revoke(sid)
    assert sessions.valid(sid) is False
    assert sessions.valid(None) is False

    expired = SessionManager(ttl_seconds=60)
    stale = expired.create()
    expired._sessions[stale] = time.time() - 1  # simulate an elapsed session
    assert expired.valid(stale) is False


def test_auth_service_reports_anonymous_state(tmp_path) -> None:
    service = AuthService(tmp_path, enabled=True)
    status = service.status(None)
    assert status == {"required": True, "configured": False, "authenticated": False}


def test_control_plane_gates_api_when_auth_enabled(tmp_path) -> None:
    auth = AuthService(tmp_path / "data", enabled=True)
    api = make_client(tmp_path, auth=auth)

    blocked = api.get("/api/v1/settings")
    assert blocked.status_code == 401
    assert blocked.json()["error"]["code"] == "unauthenticated"

    # The auth endpoints and the liveness probe stay reachable so a browser can sign in.
    assert api.get("/api/v1/auth/status").status_code == 200
    assert api.get("/api/v1/system/health").status_code == 200

    # First run: set the password, which also signs the caller in.
    setup = api.post("/api/v1/auth/setup", json={"password": PASSWORD})
    assert setup.status_code == 200
    assert setup.json()["authenticated"] is True

    # A second setup attempt is refused once a password exists.
    assert api.post("/api/v1/auth/setup", json={"password": PASSWORD}).status_code == 409

    # Now the gated API is reachable with the session cookie the client kept.
    assert api.get("/api/v1/settings").status_code == 200

    # Sign out and confirm the gate closes again.
    assert api.post("/api/v1/auth/logout").status_code == 200
    assert api.get("/api/v1/settings").status_code == 401


def test_control_plane_login_flow(tmp_path) -> None:
    auth = AuthService(tmp_path / "data", enabled=True)
    api = make_client(tmp_path, auth=auth)

    # Signing in before a password exists is a setup problem, not a bad login.
    assert api.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 409

    auth.passwords.set(PASSWORD)
    assert api.post("/api/v1/auth/login", json={"password": "nope"}).status_code == 401

    ok = api.post("/api/v1/auth/login", json={"password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["authenticated"] is True
    assert api.get("/api/v1/settings").status_code == 200


def test_change_password_requires_current_and_rotates_session(tmp_path) -> None:
    auth = AuthService(tmp_path / "data", enabled=True)
    api = make_client(tmp_path, auth=auth)
    api.post("/api/v1/auth/setup", json={"password": PASSWORD})

    assert api.post(
        "/api/v1/auth/password", json={"current": "wrong", "password": "brand-new-secret-value"}
    ).status_code == 401

    changed = api.post(
        "/api/v1/auth/password", json={"current": PASSWORD, "password": "brand-new-secret-value"}
    )
    assert changed.status_code == 200
    assert api.get("/api/v1/settings").status_code == 200

    api.post("/api/v1/auth/logout")
    assert api.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 401
    assert api.post("/api/v1/auth/login", json={"password": "brand-new-secret-value"}).status_code == 200


def test_control_plane_is_open_when_auth_is_not_attached(tmp_path) -> None:
    api = make_client(tmp_path, auth=None)
    assert api.get("/api/v1/settings").status_code == 200
    status = api.get("/api/v1/auth/status").json()
    assert status == {"required": False, "configured": True, "authenticated": True}


def test_disabled_auth_leaves_the_api_open(tmp_path) -> None:
    auth = AuthService(tmp_path / "data", enabled=False)
    api = make_client(tmp_path, auth=auth)
    assert api.get("/api/v1/settings").status_code == 200
    assert api.get("/api/v1/auth/status").json()["required"] is False
