from __future__ import annotations

import os
from pathlib import Path

from seclyst_backend.server import (
    ACCESS_TOKEN_FILE,
    LOOPBACK_HOSTS,
    Supervisor,
    TOOL_SPECS,
    _load_env_file,
    _load_or_create_access_token,
)


def test_tool_ports_are_unique_and_loopback_only() -> None:
    ports = [spec.default_port for spec in TOOL_SPECS]
    assert len(ports) == len(set(ports)) == 5
    assert LOOPBACK_HOSTS == {"127.0.0.1", "localhost"}


def test_env_file_does_not_override_process_environment(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECLYST_TEST_EXISTING=from-file\n"
        "SECLYST_TEST_NEW='from file'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SECLYST_TEST_EXISTING", "from-process")
    monkeypatch.delenv("SECLYST_TEST_NEW", raising=False)

    _load_env_file(env_file)

    assert os.environ["SECLYST_TEST_EXISTING"] == "from-process"
    assert os.environ["SECLYST_TEST_NEW"] == "from file"


def test_supervisor_redirects_mutable_engine_state_to_data() -> None:
    supervisor = Supervisor(7000, start_engines=False)
    for tool in supervisor.tools.values():
        env = supervisor._environment(tool)
        if tool.spec.id == "malware":
            assert env["SECLYST_MALWARE_DATA_DIR"].replace("\\", "/").lower().endswith("/data/malware")
        elif tool.spec.id == "ioc":
            assert env["DATABASE_URL"].replace("\\", "/").lower().endswith("/data/ioc/ioc_platform.db")
        elif tool.spec.id == "events":
            assert env["EVTX_VIEWER_DATA_DIR"].replace("\\", "/").lower().endswith("/data/events")
        elif tool.spec.id == "phishing":
            assert env["SECLYST_PHISHING_DATA_DIR"].replace("\\", "/").lower().endswith("/data/phishing")
        elif tool.spec.id == "ruleforge":
            assert env["RULEFORGE_HOME"].replace("\\", "/").lower().endswith("/data/ruleforge")
        assert "http://127.0.0.1:7000" in env["SECLYST_FRAME_ANCESTORS"]
        assert "http://localhost:7000" in env["SECLYST_FRAME_ANCESTORS"]


def test_access_token_is_reused_across_restarts(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "access_token"
    monkeypatch.setattr("seclyst_backend.server.ACCESS_TOKEN_FILE", token_file)
    monkeypatch.delenv("SECLYST_ACCESS_TOKEN", raising=False)

    first = _load_or_create_access_token()
    second = _load_or_create_access_token()

    assert first == second
    assert token_file.read_text(encoding="utf-8").strip() == first
    assert len(first) >= 20


def test_access_token_env_override(monkeypatch) -> None:
    monkeypatch.setattr("seclyst_backend.server.ACCESS_TOKEN_FILE", ACCESS_TOKEN_FILE.parent / "unused")
    monkeypatch.setenv("SECLYST_ACCESS_TOKEN", "pinned-token")
    assert _load_or_create_access_token() == "pinned-token"


def test_browser_url_follows_the_shell_host() -> None:
    supervisor = Supervisor(7000, start_engines=False)
    tool = supervisor.tools["ioc"]
    tool.access_token = "tok"

    assert tool.browser_url_for("localhost") == "http://localhost:7102/?seclyst_access=tok"
    assert tool.browser_url_for("127.0.0.1") == "http://127.0.0.1:7102/?seclyst_access=tok"
    # Anything that is not a loopback alias keeps the engine's own binding.
    assert tool.browser_url_for("example.test") == "http://127.0.0.1:7102/?seclyst_access=tok"
