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


ACCESS_DENIED_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SecLyst access required</title>
<style>html{color-scheme:dark}body{margin:0;min-height:100vh;display:grid;place-items:center;
background:#0d1117;color:#e6edf3;font:15px/1.5 system-ui,sans-serif}main{max-width:34rem;padding:2rem}
h1{font-size:1.15rem;margin:0 0 .5rem}p{margin:.35rem 0;color:#9da7b3}</style>
</head><body><main><h1>This tool opens through SecLyst</h1>
<p>The engine only accepts requests that carry the workspace access token.</p>
<p>Go back to the SecLyst dashboard and open the tool from there.</p>
</main></body></html>"""


def install_flask_access(app) -> None:
    if not required_token():
        return
    from flask import jsonify, make_response, redirect, request

    @app.before_request
    def require_seclyst_access():
        bootstrap = request.args.get("seclyst_access")
        if bootstrap and valid(bootstrap):
            response = make_response(redirect(clean_bootstrap_url(request.url), code=302))
            response.set_cookie(COOKIE_NAME, bootstrap, httponly=True, samesite="Strict", secure=False, path="/")
            return response
        supplied = request.headers.get("X-SecLyst-Access") or request.cookies.get(COOKIE_NAME)
        if valid(supplied):
            return None
        # A browser navigation gets a readable page; an API call gets JSON.
        # Both used to be a bare "Forbidden" that told the analyst nothing.
        if "text/html" in request.headers.get("Accept", "").lower():
            return make_response(ACCESS_DENIED_HTML, 403)
        return make_response(
            jsonify(
                {
                    "error": "SecLyst access required",
                    "detail": "This engine only opens through SecLyst. Return to the dashboard and open the tool there.",
                }
            ),
            403,
        )
