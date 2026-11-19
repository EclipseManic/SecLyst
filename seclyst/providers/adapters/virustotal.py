from __future__ import annotations

import base64
from email.utils import parsedate_to_datetime
from datetime import UTC, datetime
from typing import Any

import httpx


class VirusTotalAdapter:
    provider = "virustotal"
    version = "v3"

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(base_url="https://www.virustotal.com/api/v3", timeout=15)

    def lookup(
        self,
        subject_type: str,
        subject: str,
        options: dict[str, Any],
        credential: str,
    ) -> dict[str, Any]:
        path = self._path(subject_type, subject, options)
        if not path:
            return {"state": "invalid_request", "error": "Unsupported VirusTotal subject type."}
        response = self.client.get(path, headers={"x-apikey": credential, "accept": "application/json"})
        retry_after = self._retry_after(response.headers.get("retry-after"))
        if response.status_code == 404:
            return {"state": "not_found", "http_status": 404, "data": None}
        if response.status_code == 429:
            return {"state": "waiting_rate_limit", "http_status": 429, "retry_after": retry_after or 60, "data": None}
        if response.status_code >= 500:
            return {"state": "unavailable", "http_status": response.status_code, "data": None}
        if response.status_code >= 400:
            return {"state": "provider_error", "http_status": response.status_code, "data": None}
        try:
            data = response.json()
        except ValueError:
            return {"state": "provider_error", "http_status": response.status_code, "error": "Malformed JSON response."}
        return {"state": "success", "http_status": response.status_code, "data": data}

    @staticmethod
    def _path(subject_type: str, subject: str, options: dict[str, Any]) -> str:
        explicit_path = options.get("path")
        if isinstance(explicit_path, str) and explicit_path:
            allowed_prefixes = ("files/", "domains/", "ip_addresses/", "urls/")
            clean = explicit_path.lstrip("/")
            return clean if clean.startswith(allowed_prefixes) and ".." not in clean else ""
        if subject_type in {"md5", "sha1", "sha256", "file"}:
            return f"files/{subject}"
        if subject_type in {"ipv4", "ipv6", "ip"}:
            return f"ip_addresses/{subject}"
        if subject_type == "domain":
            return f"domains/{subject}"
        if subject_type == "url":
            encoded = base64.urlsafe_b64encode(subject.encode()).decode().rstrip("=")
            return f"urls/{encoded}"
        return ""

    @staticmethod
    def _retry_after(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return max(0, int(value))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return max(0, int((parsed - datetime.now(UTC)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                return None
