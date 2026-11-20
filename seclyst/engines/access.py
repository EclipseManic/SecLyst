from __future__ import annotations

import os
import secrets
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


COOKIE_NAME = "seclyst_access"


def required_token() -> str:
    return os.getenv("SECLYST_ACCESS_TOKEN", "").strip()


def valid(value: str | None) -> bool:
    expected = required_token()
    return not expected or bool(value and secrets.compare_digest(expected, value))


def cookie_value(header: str | None) -> str | None:
    if not header:
        return None
    cookie = SimpleCookie()
    cookie.load(header)
    morsel = cookie.get(COOKIE_NAME)
    return morsel.value if morsel else None


def clean_bootstrap_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if key != "seclyst_access"])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def install_flask_access(app) -> None:
    if not required_token():
        return
    from flask import abort, make_response, redirect, request

    @app.before_request
    def require_seclyst_access():
        bootstrap = request.args.get("seclyst_access")
        if bootstrap and valid(bootstrap):
            response = make_response(redirect(clean_bootstrap_url(request.url), code=302))
            response.set_cookie(COOKIE_NAME, bootstrap, httponly=True, samesite="Strict", secure=False, path="/")
            return response
        supplied = request.headers.get("X-SecLyst-Access") or request.cookies.get(COOKIE_NAME)
        if not valid(supplied):
            abort(403)
        return None
