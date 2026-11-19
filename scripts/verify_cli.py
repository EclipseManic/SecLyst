"""Verify that the documented Seclyst launcher starts and shuts down cleanly."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PORTS = (7000, 7101, 7102, 7103, 7104, 7105)


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def main() -> int:
    ready_deadline = time.monotonic() + 15
    while time.monotonic() < ready_deadline and not all(port_is_free(port) for port in PORTS):
        time.sleep(0.1)
    if not all(port_is_free(port) for port in PORTS):
        raise SystemExit("Seclyst verification ports must be free before the CLI smoke test.")

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [sys.executable, "run.py", "--no-browser"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    try:
        deadline = time.monotonic() + 45
        status = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"Seclyst launcher exited with {process.returncode}:\n{output}")
            try:
                with urllib.request.urlopen("http://127.0.0.1:7000/api/platform/status", timeout=1) as response:
                    status = json.loads(response.read().decode("utf-8"))
                if all(tool["status"] == "online" for tool in status["tools"].values()):
                    break
            except OSError:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError(f"Seclyst launcher did not become ready: {status}")
        print("Documented launcher reached five-of-five engine health.")
    finally:
        if process.poll() is None:
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not all(port_is_free(port) for port in PORTS):
        time.sleep(0.1)
    if not all(port_is_free(port) for port in PORTS):
        raise RuntimeError("The Seclyst launcher left one or more service ports occupied.")
    print("Documented launcher stopped all child engines cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
