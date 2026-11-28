"""Authentication endpoints for the single-user SecLyst control plane.

These routes are the only ones reachable without a session (see the gate in
:mod:`seclyst_backend.app`). They are intentionally small: check status, set the
password on first run, sign in, sign out, and change the password.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth import SESSION_COOKIE, AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

UNAUTHENTICATED: dict[str, Any] = {
    "code": "unauthenticated",
    "message": "Sign in to the local workspace.",
}


class PasswordBody(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class ChangePasswordBody(BaseModel):
    current: str = Field(min_length=1, max_length=1024)
    password: str = Field(min_length=1, max_length=1024)


def _service(request: Request) -> AuthService:
    service: AuthService | None = getattr(request.app.state, "auth", None)
    if service is None:
        raise HTTPException(404, detail={"code": "auth_disabled", "message": "Authentication is not enabled."})
    return service


def _anonymous_status() -> dict[str, Any]:
    # No auth service is attached: the shell is running ungated (tests or an
    # explicit opt-out) and every request is effectively authenticated.
    return {"required": False, "configured": True, "authenticated": True}


def _set_session(response: Response, sid: str, service: AuthService) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=sid,
        max_age=service.cookie_max_age,
        httponly=True,
        samesite="strict",
        secure=False,  # loopback origin is plain http
        path="/",
    )


@router.get("/status")
def auth_status(request: Request) -> dict[str, Any]:
    service: AuthService | None = getattr(request.app.state, "auth", None)
    if service is None:
        return _anonymous_status()
    return service.status(request.cookies.get(SESSION_COOKIE))


@router.post("/setup")
def auth_setup(body: PasswordBody, request: Request, response: Response) -> dict[str, Any]:
    service = _service(request)
    if not service.enabled:
        raise HTTPException(400, detail={"code": "auth_disabled", "message": "Authentication is not enabled."})
    if service.configured:
        raise HTTPException(409, detail={"code": "already_configured", "message": "A password is already set."})
    try:
        sid = service.set_password(body.password)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "weak_password", "message": str(exc)}) from exc
    _set_session(response, sid, service)
    return service.status(sid)


@router.post("/login")
def auth_login(body: PasswordBody, request: Request, response: Response) -> dict[str, Any]:
    service = _service(request)
    if not service.enabled:
        return _anonymous_status()
    if not service.configured:
        raise HTTPException(409, detail={"code": "setup_required", "message": "Set a password before signing in."})
    sid = service.login(body.password)
    if sid is None:
        raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Incorrect password."})
    _set_session(response, sid, service)
    return service.status(sid)


@router.post("/logout")
def auth_logout(request: Request, response: Response) -> dict[str, Any]:
    service: AuthService | None = getattr(request.app.state, "auth", None)
    if service is None:
        return _anonymous_status()
    service.sessions.revoke(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return service.status(None)


@router.post("/password")
def auth_change_password(body: ChangePasswordBody, request: Request, response: Response) -> dict[str, Any]:
    service = _service(request)
    sid = request.cookies.get(SESSION_COOKIE)
    if not service.sessions.valid(sid):
        raise HTTPException(401, detail=UNAUTHENTICATED)
    if not service.passwords.verify(body.current):
        raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Current password is incorrect."})
    service.sessions.revoke_all()
    try:
        new_sid = service.set_password(body.password)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "weak_password", "message": str(exc)}) from exc
    _set_session(response, new_sid, service)
    return service.status(new_sid)
