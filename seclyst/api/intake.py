"""Forward evidence from the shell's home intake to the engine that owns it.

The shell and each engine live on different loopback origins, so the browser
cannot push a ``File`` into an engine's iframe. Instead the shell posts the
evidence here and the control plane forwards it, server to server, to the
engine's own upload endpoint with the workspace access token. The engine then
runs its normal pipeline and the finished record shows up in the activity feed.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])

MAX_FILES = 25
MAX_TOTAL_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class FileTarget:
    path: str
    field: str
    headers: dict[str, str]


# The upload contract of each file-based engine. Field names and the extra
# header come from the engines themselves, not guesswork:
#   malware  run.py  POST /api/scan     multipart "malware_file"
#   phishing run.py  POST /api/analyze  multipart "email_file" + X-Requested-With
#   events   api.py  POST /api/upload   multipart "files" (repeated)
FILE_TARGETS: dict[str, FileTarget] = {
    "malware": FileTarget("/api/scan", "malware_file", {}),
    "phishing": FileTarget("/api/analyze", "email_file", {"X-Requested-With": "XMLHttpRequest"}),
    "events": FileTarget("/api/upload", "files", {}),
}

# These engines analyse text, not evidence files.
TEXT_TOOLS = {
    "ioc": "IOC Lookup takes an indicator as text, not a file.",
    "ruleforge": "RuleForge takes a rule as text, not a file.",
}


def _engine_message(response: httpx.Response) -> str:
    """The most useful sentence an engine put in its error body."""
    try:
        payload = response.json()
    except ValueError:
        return f"The engine answered HTTP {response.status_code}."
    if isinstance(payload, dict):
        for key in ("error", "detail", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                message = value.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
    return f"The engine answered HTTP {response.status_code}."


@router.post("")
async def intake(
    request: Request,
    tool: str = Form(...),
    files: list[UploadFile] = File(default=[]),
):
    tool = tool.strip().lower()
    if tool in TEXT_TOOLS:
        raise HTTPException(
            status_code=422,
            detail={"code": "file_intake_not_supported", "message": TEXT_TOOLS[tool]},
        )

    target = FILE_TARGETS.get(tool)
    supervisor = getattr(request.app.state, "supervisor", None)
    process = getattr(supervisor, "tools", {}).get(tool) if supervisor is not None else None
    if target is None or process is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_tool", "message": f"No file intake is configured for {tool!r}."},
        )
    if getattr(process, "start_error", ""):
        raise HTTPException(
            status_code=503,
            detail={"code": "engine_unavailable", "message": process.start_error},
        )
    if not files:
        raise HTTPException(
            status_code=422,
            detail={"code": "no_files", "message": "Choose at least one file to upload."},
        )
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=413,
            detail={"code": "too_many_files", "message": f"Upload at most {MAX_FILES} files at a time."},
        )

    payloads: list[tuple[str, bytes, str]] = []
    total = 0
    for upload in files:
        data = await upload.read()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "upload_too_large", "message": "The upload is larger than the local intake limit."},
            )
        payloads.append(
            (
                upload.filename or "upload.bin",
                data,
                upload.content_type or "application/octet-stream",
            )
        )

    url = process.url.rstrip("/") + target.path
    headers = {"X-SecLyst-Access": process.access_token, **target.headers}
    accepted: list[dict] = []
    rejected: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            if tool == "events":
                # The events engine accepts many files as one investigation.
                response = await client.post(
                    url,
                    files=[(target.field, item) for item in payloads],
                    headers=headers,
                )
                record = {
                    "name": payloads[0][0] if len(payloads) == 1 else f"{len(payloads)} files",
                    "status": response.status_code,
                }
                if response.is_success:
                    accepted.append(record)
                else:
                    record["message"] = _engine_message(response)
                    rejected.append(record)
            else:
                # Malware and phishing start one run per file.
                for item in payloads:
                    response = await client.post(
                        url,
                        files={target.field: item},
                        headers=headers,
                    )
                    record = {"name": item[0], "status": response.status_code}
                    if response.is_success:
                        accepted.append(record)
                    else:
                        record["message"] = _engine_message(response)
                        rejected.append(record)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "engine_unreachable", "message": f"Could not reach the {tool} engine: {exc}"},
        ) from exc

    if not accepted:
        message = rejected[0].get("message", "The engine rejected the upload.") if rejected else "The engine rejected the upload."
        raise HTTPException(status_code=502, detail={"code": "intake_rejected", "message": message})

    return {"tool": tool, "started": len(accepted), "accepted": accepted, "rejected": rejected}