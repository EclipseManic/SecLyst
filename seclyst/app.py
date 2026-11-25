"""FastAPI application for the SecLyst control plane and shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .api.auth import router as auth_router
from .api.jobs import router as jobs_router
from .api.internal import router as internal_router
from .api.artifacts import router as artifacts_router
from .api.runs import router as runs_router
from .api.settings import router as settings_router
from .auth import SESSION_COOKIE, AuthService
from .jobs.service import JobService

# Reachable without a session: the auth endpoints themselves (so a browser can
# sign in) and the liveness probe. Every other /api/ path is gated when auth is
# enabled.
_AUTH_PUBLIC_PREFIX = "/api/v1/auth/"


def create_app(
    *,
    supervisor: Any,
    job_service: JobService,
    durable_jobs_enabled: bool,
    web_root: Path,
    engine_tokens: dict[str, str] | None = None,
    provider_broker: Any = None,
    artifact_store: Any = None,
    runtime_dir: Path | None = None,
    auth: AuthService | None = None,
) -> FastAPI:
    app = FastAPI(title="SecLyst Control Plane", version=__version__, docs_url="/api/docs", redoc_url=None)
    app.state.supervisor = supervisor
    app.state.job_service = job_service
    app.state.durable_jobs_enabled = durable_jobs_enabled
    app.state.web_root = web_root.resolve()
    app.state.engine_tokens = engine_tokens or {}
    app.state.provider_broker = provider_broker
    app.state.artifact_store = artifact_store
    app.state.runtime_dir = (runtime_dir or web_root.parent).resolve()
    app.state.auth = auth
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(internal_router)
    app.include_router(artifacts_router)
    app.include_router(runs_router)
    app.include_router(settings_router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if auth is not None and auth.enabled:
            path = request.url.path
            is_public = path.startswith(_AUTH_PUBLIC_PREFIX) or path == "/api/v1/system/health"
            if path.startswith("/api/") and not is_public:
                if not auth.sessions.valid(request.cookies.get(SESSION_COOKIE)):
                    return JSONResponse(
                        status_code=401,
                        content={"error": {"code": "unauthenticated", "message": "Sign in to the local workspace."}},
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
                    )
        response = await call_next(request)
        tools = supervisor.tools.values()
        frame_sources = " ".join(tool.url.rstrip("/") for tool in tools)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            f"connect-src 'self' {frame_sources}; "
            f"frame-src {frame_sources}; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/api/platform/status")
    @app.get("/api/platform/health")
    @app.get("/api/platform/tools")
    def platform_status() -> dict[str, Any]:
        return supervisor.status()

    @app.get("/api/platform/summary")
    def platform_summary() -> dict[str, Any]:
        return supervisor.summary()

    @app.get("/api/v1/system/health")
    def control_plane_health() -> dict[str, Any]:
        return {
            "product": "SecLyst",
            "version": __version__,
            "durable_jobs": durable_jobs_enabled,
            "status": "ok",
        }

    @app.exception_handler(HTTPException)
    async def http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)

    @app.get("/{path:path}")
    async def static_or_spa(path: str):
        relative = unquote(path).lstrip("/")
        candidate = (app.state.web_root / relative).resolve()
        if not candidate.is_relative_to(app.state.web_root):
            raise HTTPException(status_code=403, detail={"code": "forbidden_path", "message": "Path is outside the web root."})
        if relative and candidate.is_file():
            return FileResponse(candidate)
        index = app.state.web_root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=503, detail={"code": "web_build_missing", "message": "SecLyst web build is missing."})
        return FileResponse(index)

    return app
