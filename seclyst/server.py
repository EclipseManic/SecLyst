"""Local Seclyst service supervisor and web server.

Each copied engine continues to serve its own interface. Seclyst starts those
interfaces on dedicated loopback ports, exposes their live status to the shell,
and serves the built React application from one stable entry point.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from . import __version__


ROOT = Path(__file__).resolve().parent.parent
ENGINES = ROOT / "engines"
RUNTIME = ROOT / "runtime"
WEB_DIST = ROOT / "apps" / "web" / "dist"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ToolSpec:
    id: str
    name: str
    port_env: str
    default_port: int
    directory: Path
    health_path: str = "/api/health"


@dataclass
class ToolProcess:
    spec: ToolSpec
    port: int
    process: subprocess.Popen[str] | None = None
    log_handle: Any = None
    start_error: str = ""
    started_at: float | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"


TOOL_SPECS = (
    ToolSpec("malware", "Malware Analyzer", "SECLYST_MALWARE_PORT", 7101, ENGINES / "malware"),
    ToolSpec("ioc", "IOC Lookup", "SECLYST_IOC_PORT", 7102, ENGINES / "ioc"),
    ToolSpec("events", "Event Analyzer", "SECLYST_EVENTS_PORT", 7103, ENGINES / "events"),
    ToolSpec("phishing", "Phishing Detector", "SECLYST_PHISHING_PORT", 7104, ENGINES / "phishing"),
    ToolSpec("ruleforge", "RuleForge", "SECLYST_RULEFORGE_PORT", 7105, ENGINES / "ruleforge"),
)


COLLECTION_ENDPOINTS = {
    "malware": "/api/scans",
    "ioc": "/api/recent",
    "events": "/api/investigations",
    "phishing": "/api/scans?limit=20",
    "ruleforge": "/api/history?limit=20",
}


def _load_env_file(path: Path) -> None:
    """Load a small, non-interpolating local .env without overriding the OS."""
    if not path.is_file():
        return
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise SystemExit(f"Invalid .env line {line_number}: expected NAME=value")
        name, value = line.split("=", 1)
        name = name.strip()
        if not ENV_NAME.fullmatch(name):
            raise SystemExit(f"Invalid .env name on line {line_number}: {name!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


def _configured_port(spec: ToolSpec) -> int:
    value = os.getenv(spec.port_env, str(spec.default_port))
    try:
        port = int(value)
    except ValueError as exc:
        raise SystemExit(f"{spec.port_env} must be a port, not {value!r}.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit(f"{spec.port_env} must be between 1 and 65535.")
    return port


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


class Supervisor:
    def __init__(self, shell_port: int, *, start_engines: bool = True) -> None:
        self.shell_port = shell_port
        self.start_engines = start_engines
        self.tools = {
            spec.id: ToolProcess(spec=spec, port=_configured_port(spec))
            for spec in TOOL_SPECS
        }
        self._lock = threading.Lock()

    def _environment(self, tool: ToolProcess) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "PYTHONUNBUFFERED": "1",
            "DISABLE_AUTO_OPEN": "1",
            "SECLYST_FRAME_ANCESTORS": " ".join((
                f"http://127.0.0.1:{self.shell_port}",
                f"http://localhost:{self.shell_port}",
                "http://127.0.0.1:5173",
            )),
        })
        data_dir = (RUNTIME / tool.spec.id).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)

        if tool.spec.id == "malware":
            env.update({
                "PORT": str(tool.port),
                "SECLYST_MALWARE_DATA_DIR": str(data_dir),
                "SOCKETIO_CORS_ORIGINS": " ".join((tool.url.rstrip("/"), tool.url.replace("127.0.0.1", "localhost").rstrip("/"))),
            })
        elif tool.spec.id == "ioc":
            database = (data_dir / "ioc_platform.db").as_posix()
            env.update({
                "HOST": "127.0.0.1",
                "PORT": str(tool.port),
                "IOC_ENV_FILE": "",
                "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
                "CACHE_DIR": str(data_dir / "cache"),
                "CORS_ORIGINS": ",".join((tool.url.rstrip("/"), f"http://127.0.0.1:{self.shell_port}", "http://127.0.0.1:5173")),
                "TRUSTED_HOSTS": "127.0.0.1,localhost",
                "BASE_URL": tool.url.rstrip("/"),
            })
        elif tool.spec.id == "events":
            env.update({
                "EVTX_VIEWER_HOST": "127.0.0.1",
                "EVTX_VIEWER_PORT": str(tool.port),
                "EVTX_VIEWER_AUTO_LAUNCH": "false",
                "EVTX_VIEWER_DATA_DIR": str(data_dir),
                "EVTX_VIEWER_DB_PATH": str(data_dir / "evtx_viewer.db"),
                "EVTX_VIEWER_UPLOADS_DIR": str(data_dir / "uploads"),
            })
        elif tool.spec.id == "phishing":
            env.update({
                "PORT": str(tool.port),
                "SECLYST_PHISHING_DATA_DIR": str(data_dir),
            })
        elif tool.spec.id == "ruleforge":
            env["RULEFORGE_HOME"] = str(data_dir)
        return env

    def _command(self, tool: ToolProcess) -> list[str]:
        command = [sys.executable, "run.py"]
        if tool.spec.id == "ruleforge":
            command.extend(("serve", "--port", str(tool.port), "--no-browser"))
        return command

    def start_all(self) -> None:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        (RUNTIME / "logs").mkdir(parents=True, exist_ok=True)
        if not self.start_engines:
            return
        for tool in self.tools.values():
            self._start(tool)

    def _start(self, tool: ToolProcess) -> None:
        if not tool.spec.directory.is_dir():
            tool.start_error = f"Missing engine directory: {tool.spec.directory}"
            return
        if not _port_is_free(tool.port):
            tool.start_error = f"Port {tool.port} is already in use."
            return

        log_path = RUNTIME / "logs" / f"{tool.spec.id}.log"
        tool.log_handle = log_path.open("a", encoding="utf-8")
        try:
            tool.process = subprocess.Popen(
                self._command(tool),
                cwd=tool.spec.directory,
                env=self._environment(tool),
                stdout=tool.log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            tool.started_at = time.time()
        except OSError as exc:
            tool.start_error = str(exc)
            tool.log_handle.close()
            tool.log_handle = None

    def stop_all(self) -> None:
        with self._lock:
            tools = list(reversed(tuple(self.tools.values())))
            for tool in tools:
                process = tool.process
                if process is not None and process.poll() is None:
                    process.terminate()
            deadline = time.monotonic() + 5.0
            for tool in tools:
                process = tool.process
                if process is not None and process.poll() is None:
                    remaining = max(0.0, deadline - time.monotonic())
                    try:
                        process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        process.kill()
            for tool in tools:
                if tool.log_handle is not None:
                    tool.log_handle.close()
                    tool.log_handle = None

    @staticmethod
    def _request_json(url: str, timeout: float = 0.8) -> Any:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": f"Seclyst/{__version__}"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _tool_status(self, tool: ToolProcess) -> dict[str, Any]:
        exit_code = tool.process.poll() if tool.process is not None else None
        if tool.start_error:
            return {
                "id": tool.spec.id,
                "name": tool.spec.name,
                "url": tool.url,
                "port": tool.port,
                "status": "error",
                "detail": tool.start_error,
            }
        if tool.process is not None and exit_code is not None:
            return {
                "id": tool.spec.id,
                "name": tool.spec.name,
                "url": tool.url,
                "port": tool.port,
                "status": "error",
                "detail": f"Engine exited with code {exit_code}. See runtime/logs/{tool.spec.id}.log.",
            }
        try:
            health = self._request_json(tool.url.rstrip("/") + tool.spec.health_path)
            return {
                "id": tool.spec.id,
                "name": tool.spec.name,
                "url": tool.url,
                "port": tool.port,
                "status": "online",
                "detail": health,
            }
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            status = "starting" if tool.process is not None and exit_code is None else "offline"
            return {
                "id": tool.spec.id,
                "name": tool.spec.name,
                "url": tool.url,
                "port": tool.port,
                "status": status,
                "detail": str(exc),
            }

    def status(self) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=len(self.tools)) as executor:
            rows = list(executor.map(self._tool_status, self.tools.values()))
        return {
            "product": "Seclyst",
            "version": __version__,
            "generatedAt": int(time.time() * 1000),
            "tools": {row["id"]: row for row in rows},
        }

    def _collection(self, tool: ToolProcess) -> dict[str, Any]:
        endpoint = COLLECTION_ENDPOINTS[tool.spec.id]
        try:
            payload = self._request_json(tool.url.rstrip("/") + endpoint, timeout=1.5)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return {"count": 0, "records": [], "available": False, "detail": str(exc)}

        if isinstance(payload, list):
            records = payload
            total = len(records)
        elif tool.spec.id in {"malware", "phishing"}:
            records = payload.get("scans", [])
            total = int(payload.get("total", len(records)))
        elif tool.spec.id == "ruleforge":
            records = payload.get("entries", [])
            total = int(payload.get("total", len(records)))
        else:
            records = []
            total = 0
        return {"count": total, "records": records[:20], "available": True}

    def summary(self) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=len(self.tools)) as executor:
            values = list(executor.map(self._collection, self.tools.values()))
        return {
            "generatedAt": int(time.time() * 1000),
            "collections": {
                tool_id: value for tool_id, value in zip(self.tools, values, strict=True)
            },
        }


class SeclystHandler(SimpleHTTPRequestHandler):
    supervisor: Supervisor
    web_root: Path

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path in {"/api/platform/status", "/api/platform/health", "/api/platform/tools"}:
            self._json(self.supervisor.status())
            return
        if path == "/api/platform/summary":
            self._json(self.supervisor.summary())
            return

        relative = unquote(path).lstrip("/")
        candidate = (self.web_root / relative).resolve()
        try:
            inside = candidate.is_relative_to(self.web_root.resolve())
        except AttributeError:  # pragma: no cover - Python 3.8 compatibility
            inside = str(candidate).startswith(str(self.web_root.resolve()))
        if not inside:
            self.send_error(HTTPStatus.FORBIDDEN.value)
            return
        if path != "/" and candidate.is_file():
            super().do_GET()
            return
        self.path = "/index.html"
        super().do_GET()

    def end_headers(self) -> None:
        frame_sources = " ".join(tool.url.rstrip("/") for tool in self.supervisor.tools.values())
        connect_sources = frame_sources
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            f"connect-src 'self' {connect_sources}; "
            f"frame-src {frame_sources}; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        if self.path.startswith("/api/") or args[1] not in {"200", "304"}:
            super().log_message(fmt, *args)


def build_http_server(host: str, port: int, supervisor: Supervisor) -> ThreadingHTTPServer:
    SeclystHandler.supervisor = supervisor
    SeclystHandler.web_root = WEB_DIST
    handler = partial(SeclystHandler, directory=str(WEB_DIST))
    return ThreadingHTTPServer((host, port), handler)


def _open_browser_when_ready(url: str) -> None:
    def _open() -> None:
        for _ in range(100):
            try:
                with urllib.request.urlopen(url, timeout=0.2):
                    webbrowser.open(url)
                    return
            except OSError:
                time.sleep(0.05)

    threading.Thread(target=_open, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the Seclyst analyst workbench.")
    parser.add_argument("--host", default="127.0.0.1", choices=sorted(LOOPBACK_HOSTS))
    parser.add_argument("--port", type=int, default=7000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-engines", action="store_true", help="serve the shell without starting engines")
    args = parser.parse_args(argv)

    _load_env_file(ROOT / ".env")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not WEB_DIST.joinpath("index.html").is_file():
        print("Seclyst web assets are not built.", file=sys.stderr)
        print("Run: python scripts/setup.py --skip-python", file=sys.stderr)
        return 2
    if not _port_is_free(args.port):
        print(f"Seclyst shell port {args.port} is already in use.", file=sys.stderr)
        return 2

    supervisor = Supervisor(args.port, start_engines=not args.no_engines)
    supervisor.start_all()
    server = build_http_server(args.host, args.port, supervisor)
    url = f"http://{args.host}:{args.port}/"

    stop_requested = threading.Event()

    def _stop(_signum: int, _frame: Any) -> None:
        if not stop_requested.is_set():
            stop_requested.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _stop)

    print(f"Seclyst {__version__} is available at {url}")
    for tool in supervisor.tools.values():
        detail = tool.start_error or tool.url
        print(f"  {tool.spec.name:<20} {detail}")
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        _open_browser_when_ready(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        supervisor.stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
