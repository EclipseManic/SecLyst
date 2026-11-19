from __future__ import annotations

import os
from pathlib import Path

from seclyst.server import LOOPBACK_HOSTS, Supervisor, TOOL_SPECS, _load_env_file


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


def test_supervisor_redirects_mutable_engine_state_to_runtime() -> None:
    supervisor = Supervisor(7000, start_engines=False)
    for tool in supervisor.tools.values():
        env = supervisor._environment(tool)
        if tool.spec.id == "malware":
            assert env["SECLYST_MALWARE_DATA_DIR"].replace("\\", "/").lower().endswith("/runtime/malware")
        elif tool.spec.id == "ioc":
            assert env["DATABASE_URL"].replace("\\", "/").lower().endswith("/runtime/ioc/ioc_platform.db")
        elif tool.spec.id == "events":
            assert env["EVTX_VIEWER_DATA_DIR"].replace("\\", "/").lower().endswith("/runtime/events")
        elif tool.spec.id == "phishing":
            assert env["SECLYST_PHISHING_DATA_DIR"].replace("\\", "/").lower().endswith("/runtime/phishing")
        elif tool.spec.id == "ruleforge":
            assert env["RULEFORGE_HOME"].replace("\\", "/").lower().endswith("/runtime/ruleforge")
        assert "http://127.0.0.1:7000" in env["SECLYST_FRAME_ANCESTORS"]
