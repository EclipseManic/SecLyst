from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from seclyst.server import Supervisor, build_http_server


@pytest.fixture(scope="module")
def platform() -> Iterator[tuple[Supervisor, str]]:
    supervisor = Supervisor(7000)
    supervisor.start_all()
    server = build_http_server("127.0.0.1", 7000, supervisor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    deadline = time.monotonic() + 40
    last_status = None
    while time.monotonic() < deadline:
        last_status = supervisor.status()
        if all(tool["status"] == "online" for tool in last_status["tools"].values()):
            break
        time.sleep(0.25)
    else:
        pytest.fail(f"Engines did not become ready: {last_status}")

    try:
        yield supervisor, "http://127.0.0.1:7000"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        supervisor.stop_all()


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


@pytest.mark.integration
def test_platform_reports_all_five_engines_online(platform) -> None:
    _supervisor, base_url = platform
    status = get_json(base_url + "/api/platform/status")
    assert status["product"] == "Seclyst"
    assert set(status["tools"]) == {"malware", "ioc", "events", "phishing", "ruleforge"}
    assert {tool["status"] for tool in status["tools"].values()} == {"online"}


@pytest.mark.integration
def test_every_original_interface_is_served_as_html(platform) -> None:
    supervisor, _base_url = platform
    for tool_id, tool in supervisor.tools.items():
        with urllib.request.urlopen(tool.url, timeout=5) as response:
            body = response.read(8192).decode("utf-8", "replace").lower()
            assert response.status == 200, tool_id
            assert "<html" in body or "<!doctype html" in body, tool_id


@pytest.mark.integration
def test_every_history_collection_is_live(platform) -> None:
    _supervisor, base_url = platform
    summary = get_json(base_url + "/api/platform/summary")
    assert set(summary["collections"]) == {"malware", "ioc", "events", "phishing", "ruleforge"}
    assert all(collection["available"] for collection in summary["collections"].values())
    assert all(collection["count"] >= 0 for collection in summary["collections"].values())


@pytest.mark.integration
def test_restricted_tools_allow_only_seclyst_frame_ancestors(platform) -> None:
    supervisor, _base_url = platform
    for tool_id in ("ioc", "ruleforge"):
        with urllib.request.urlopen(supervisor.tools[tool_id].url, timeout=5) as response:
            assert response.headers.get("X-Frame-Options") is None
            policy = response.headers["Content-Security-Policy"]
            assert "frame-ancestors http://127.0.0.1:7000" in policy
            assert "frame-ancestors *" not in policy


@pytest.mark.integration
def test_shell_security_headers_and_spa_fallback(platform) -> None:
    supervisor, base_url = platform
    with urllib.request.urlopen(base_url + "/not-a-file", timeout=5) as response:
        body = response.read().decode("utf-8")
        assert response.status == 200
        assert "<title>Seclyst" in body
        assert response.headers["X-Frame-Options"] == "DENY"
        malware_origin = supervisor.tools["malware"].url.rstrip("/")
        assert f"frame-src {malware_origin}" in response.headers["Content-Security-Policy"]


@pytest.mark.integration
def test_static_path_traversal_is_refused(platform) -> None:
    _supervisor, base_url = platform
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(base_url + "/%2e%2e/README.md", timeout=5)
    assert error.value.code == 403
