"""The home-intake proxy: the shell hands a file to the control plane, which
forwards it to the engine that owns it.

These tests pin the three things that silently break uploads: the multipart
field name, the per-engine extra header, and the destination path. A real
engine is never started; the outgoing ``httpx`` client is replaced with a fake
that records what would have been sent.
"""

from __future__ import annotations

import types

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seclyst_backend.api import intake as intake_module


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: object = None) -> None:
        self.status_code = status_code
        self._payload = payload

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class FakeAsyncClient:
    """Records every POST and answers with a queued response."""

    calls: list[dict] = []
    response: FakeResponse = FakeResponse(200, {"status": "running"})
    raises: Exception | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def post(self, url, files=None, headers=None):
        if type(self).raises is not None:
            raise type(self).raises
        type(self).calls.append({"url": url, "files": files, "headers": headers})
        return type(self).response


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[FakeAsyncClient]:
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(200, {"status": "running"})
    FakeAsyncClient.raises = None
    # Replace only this module's httpx, so TestClient keeps the real library.
    fake_module = types.SimpleNamespace(
        AsyncClient=FakeAsyncClient,
        HTTPError=httpx.HTTPError,
    )
    monkeypatch.setattr(intake_module, "httpx", fake_module)
    return FakeAsyncClient


class StubProcess:
    def __init__(self, port: int, token: str, start_error: str = "") -> None:
        self.port = port
        self.access_token = token
        self.start_error = start_error

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"


class StubSupervisor:
    def __init__(self, tools: dict[str, StubProcess]) -> None:
        self.tools = tools


DEFAULT_TOOLS = {
    "malware": StubProcess(7101, "tok-malware"),
    "phishing": StubProcess(7104, "tok-phishing"),
    "events": StubProcess(7103, "tok-events"),
}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(intake_module.router)
    app.state.supervisor = StubSupervisor(dict(DEFAULT_TOOLS))
    return TestClient(app)


def test_text_tool_is_rejected(client: TestClient, fake_http: type[FakeAsyncClient]) -> None:
    response = client.post(
        "/api/v1/intake",
        data={"tool": "ioc"},
        files={"files": ("indicator.txt", b"8.8.8.8", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "file_intake_not_supported"
    assert fake_http.calls == []


def test_unknown_tool_is_rejected(client: TestClient, fake_http: type[FakeAsyncClient]) -> None:
    response = client.post(
        "/api/v1/intake",
        data={"tool": "database"},
        files={"files": ("x.bin", b"x", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unknown_tool"
    assert fake_http.calls == []


def test_missing_files_is_rejected(client: TestClient, fake_http: type[FakeAsyncClient]) -> None:
    response = client.post("/api/v1/intake", data={"tool": "malware"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_files"
    assert fake_http.calls == []


def test_malware_forwards_one_run_per_file(
    client: TestClient, fake_http: type[FakeAsyncClient]
) -> None:
    response = client.post(
        "/api/v1/intake",
        data={"tool": "malware"},
        files=[
            ("files", ("one.bin", b"AAA", "application/octet-stream")),
            ("files", ("two.bin", b"BBB", "application/octet-stream")),
        ],
    )
    assert response.status_code == 200
    assert response.json()["started"] == 2

    assert len(fake_http.calls) == 2
    for call in fake_http.calls:
        assert call["url"] == "http://127.0.0.1:7101/api/scan"
        assert call["headers"]["X-SecLyst-Access"] == "tok-malware"
        assert list(call["files"].keys()) == ["malware_file"]
    assert fake_http.calls[0]["files"]["malware_file"][0] == "one.bin"


def test_phishing_forwards_email_field_and_same_origin_header(
    client: TestClient, fake_http: type[FakeAsyncClient]
) -> None:
    response = client.post(
        "/api/v1/intake",
        data={"tool": "phishing"},
        files={"files": ("mail.eml", b"From: x", "message/rfc822")},
    )
    assert response.status_code == 200
    assert response.json()["started"] == 1

    call = fake_http.calls[0]
    assert call["url"] == "http://127.0.0.1:7104/api/analyze"
    assert call["headers"]["X-Requested-With"] == "XMLHttpRequest"
    assert call["headers"]["X-SecLyst-Access"] == "tok-phishing"
    assert list(call["files"].keys()) == ["email_file"]


def test_events_sends_all_files_as_one_investigation(
    client: TestClient, fake_http: type[FakeAsyncClient]
) -> None:
    response = client.post(
        "/api/v1/intake",
        data={"tool": "events"},
        files=[
            ("files", ("a.evtx", b"a", "application/octet-stream")),
            ("files", ("b.evtx", b"b", "application/octet-stream")),
        ],
    )
    assert response.status_code == 200
    assert response.json()["started"] == 1

    # One investigation means one request carrying both files under "files".
    assert len(fake_http.calls) == 1
    call = fake_http.calls[0]
    assert call["url"] == "http://127.0.0.1:7103/api/upload"
    assert call["headers"]["X-SecLyst-Access"] == "tok-events"
    assert isinstance(call["files"], list)
    assert [field for field, _ in call["files"]] == ["files", "files"]


def test_engine_rejection_surfaces_its_message(
    client: TestClient, fake_http: type[FakeAsyncClient]
) -> None:
    fake_http.response = FakeResponse(400, {"error": "Upload an .eml file before running analysis."})
    response = client.post(
        "/api/v1/intake",
        data={"tool": "phishing"},
        files={"files": ("notes.txt", b"nope", "text/plain")},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "intake_rejected"
    assert "eml" in response.json()["detail"]["message"]


def test_unreachable_engine_reports_502(
    client: TestClient, fake_http: type[FakeAsyncClient]
) -> None:
    fake_http.raises = httpx.ConnectError("connection refused")
    response = client.post(
        "/api/v1/intake",
        data={"tool": "malware"},
        files={"files": ("one.bin", b"AAA", "application/octet-stream")},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "engine_unreachable"


def test_stopped_engine_is_unavailable() -> None:
    app = FastAPI()
    app.include_router(intake_module.router)
    tools = dict(DEFAULT_TOOLS)
    tools["malware"] = StubProcess(7101, "tok-malware", start_error="Engine failed to start")
    app.state.supervisor = StubSupervisor(tools)
    with TestClient(app) as stopped:
        response = stopped.post(
            "/api/v1/intake",
            data={"tool": "malware"},
            files={"files": ("one.bin", b"AAA", "application/octet-stream")},
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "engine_unavailable"
