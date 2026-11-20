from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from ..providers.credentials import CredentialStore, PROVIDER_ENV_KEYS

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
TOOLS = {"malware", "ioc", "events", "phishing", "ruleforge"}


class ProviderSecret(BaseModel):
    secret: str = Field(min_length=1, max_length=4096)


class ToolSettings(BaseModel):
    values: dict[str, bool | int | float | str] = Field(default_factory=dict)


def config_path(request: Request) -> Path:
    return request.app.state.runtime_dir / "settings.json"


def load(request: Request) -> dict:
    path = config_path(request)
    if not path.is_file():
        return {"tools": {tool: {} for tool in TOOLS}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tools": {tool: {} for tool in TOOLS}}


def save(request: Request, data: dict) -> None:
    path = config_path(request)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@router.get("")
def settings(request: Request):
    credentials = CredentialStore()
    providers = sorted(PROVIDER_ENV_KEYS)
    return {
        **load(request),
        "providers": {provider: {"configured": credentials.configured(provider)} for provider in providers},
    }


@router.put("/tools/{tool}")
def update_tool(tool: str, body: ToolSettings, request: Request):
    if tool not in TOOLS:
        raise HTTPException(404, detail={"code": "unknown_tool", "message": "Unknown tool."})
    data = load(request)
    data.setdefault("tools", {})[tool] = body.values
    save(request, data)
    return {"tool": tool, "values": body.values, "restart_required": True}


@router.post("/providers/{provider}")
def set_provider(provider: str, body: ProviderSecret):
    if provider not in PROVIDER_ENV_KEYS:
        raise HTTPException(404, detail={"code": "unknown_provider", "message": "Unknown provider."})
    CredentialStore().set(provider, body.secret)
    return {"provider": provider, "configured": True}


@router.delete("/providers/{provider}")
def delete_provider(provider: str):
    if provider not in PROVIDER_ENV_KEYS:
        raise HTTPException(404, detail={"code": "unknown_provider", "message": "Unknown provider."})
    CredentialStore().remove(provider)
    return {"provider": provider, "configured": False}
