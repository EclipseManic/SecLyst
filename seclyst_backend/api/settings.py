from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..providers.credentials import CredentialStore, PROVIDER_ENV_KEYS

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

PROVIDER_TOOLS = {
    "virustotal": ["malware", "ioc", "phishing"],
    "urlscan": ["ioc", "phishing"],
    "hybrid_analysis": ["malware", "ioc"],
    "filescan": ["malware", "ioc"],
    "abuseipdb": ["ioc"],
    "shodan": ["ioc"],
    "otx": ["ioc"],
    "greynoise": ["ioc"],
    "censys": ["ioc"],
    "ipinfo": ["ioc"],
    "nvd": ["ioc"],
    "etherscan": ["ioc"],
    "abstractapi": ["phishing"],
    "ipqualityscore": ["phishing"],
    "hunter": ["phishing"],
    "malwarebazaar": ["ioc"],
    "threatfox": ["ioc"],
    "urlhaus": ["ioc"],
    "triage": ["malware", "ioc"],
    "chainabuse": ["ioc"],
    "hudson_rock": ["ioc"],
}


def field(label: str, kind: str, default: Any, description: str, env: str, **limits: Any) -> dict[str, Any]:
    return {"label": label, "type": kind, "default": default, "description": description, "env": env, **limits}


TOOL_SCHEMAS = {
    "malware": {
        "online_enrichment": field(
            "Online enrichment",
            "boolean",
            False,
            "Query configured threat-intelligence providers.",
            "SECLYST_MALWARE_ONLINE",
        ),
        "submit_unknown_samples": field(
            "Submit unknown samples",
            "boolean",
            False,
            "Allow explicit provider sample submission. Keep disabled for private files.",
            "SECLYST_MALWARE_SUBMIT_UNKNOWN",
        ),
        "max_upload_mb": field(
            "Maximum upload",
            "integer",
            100,
            "Maximum accepted sample size in MB.",
            "SECLYST_MALWARE_MAX_UPLOAD_MB",
            min=1,
            max=1024,
        ),
        "yara_rules_path": field(
            "YARA rules path",
            "string",
            "data/rules.yar",
            "Rules file relative to the Malware engine.",
            "SECLYST_MALWARE_YARA_RULES",
        ),
    },
    "ioc": {
        "active_port_scan": field(
            "Active port scanning", "boolean", False, "Permit active network probes.", "ENABLE_ACTIVE_PORT_SCAN"
        ),
        "url_content_fetch": field(
            "URL content fetching", "boolean", False, "Permit fetching remote URL content.", "ENABLE_URL_CONTENT_FETCH"
        ),
        "cache_ttl_seconds": field(
            "Cache TTL",
            "integer",
            900,
            "Default provider cache freshness in seconds.",
            "CACHE_TTL_SECONDS",
            min=0,
            max=86400,
        ),
        "provider_concurrency": field(
            "Provider concurrency",
            "integer",
            8,
            "Maximum simultaneous provider lookups.",
            "MAX_PROVIDER_CONCURRENCY",
            min=1,
            max=64,
        ),
        "batch_limit": field(
            "Batch IOC limit", "integer", 100, "Maximum indicators in one batch.", "BATCH_MAX_IOCS", min=1, max=1000
        ),
    },
    "events": {
        "max_upload_mb": field(
            "Maximum EVTX file",
            "integer",
            100,
            "Maximum size per EVTX file in MB.",
            "EVTX_VIEWER_MAX_UPLOAD_MB",
            min=1,
            max=4096,
        ),
        "max_files_per_upload": field(
            "Files per upload",
            "integer",
            500,
            "Maximum EVTX files in one upload.",
            "EVTX_VIEWER_MAX_FILES",
            min=1,
            max=5000,
        ),
        "max_request_mb": field(
            "Maximum request",
            "integer",
            2048,
            "Combined request ceiling in MB.",
            "EVTX_VIEWER_MAX_REQUEST_MB",
            min=1,
            max=16384,
        ),
        "page_limit": field(
            "Events per page",
            "integer",
            200,
            "Rows loaded by the Events interface.",
            "EVTX_VIEWER_PAGE_LIMIT",
            min=25,
            max=2000,
        ),
        "max_events_per_file": field(
            "Events per file",
            "integer",
            0,
            "Per-file event ceiling; zero means unlimited.",
            "EVTX_VIEWER_MAX_EVENTS_PER_FILE",
            min=0,
            max=50000000,
        ),
        "store_raw": field(
            "Store raw event XML", "boolean", False, "Retain raw XML for detailed forensics.", "EVTX_VIEWER_STORE_RAW"
        ),
        "concurrent_ingest": field(
            "Concurrent ingestion",
            "integer",
            2,
            "Simultaneous ingestion jobs.",
            "EVTX_VIEWER_CONCURRENT_INGEST",
            min=1,
            max=16,
        ),
        "delete_after_ingest": field(
            "Delete uploaded copies",
            "boolean",
            True,
            "Remove temporary EVTX copies after ingestion.",
            "EVTX_VIEWER_DELETE_AFTER_INGEST",
        ),
    },
    "phishing": {
        "external_enrichment": field(
            "External enrichment", "boolean", False, "Use configured reputation providers.", "SECLYST_PHISHING_EXTERNAL"
        ),
        "resolve_redirects": field(
            "Resolve URL redirects",
            "boolean",
            False,
            "Follow redirect chains during URL analysis.",
            "SECLYST_PHISHING_REDIRECTS",
        ),
        "max_upload_mb": field(
            "Maximum email size", "integer", 25, "Maximum EML or MSG upload in MB.", "MAX_UPLOAD_MB", min=1, max=250
        ),
        "workers": field(
            "Analysis workers",
            "integer",
            4,
            "Parallel phishing-analysis worker count.",
            "PHISHING_WORKERS",
            min=1,
            max=32,
        ),
        "vt_delay_seconds": field(
            "VirusTotal delay", "integer", 16, "Delay between VirusTotal requests.", "VT_DELAY_SECONDS", min=0, max=300
        ),
        "max_vt_items": field(
            "VirusTotal item limit",
            "integer",
            10,
            "Maximum enriched artifacts per email.",
            "MAX_VT_ITEMS",
            min=0,
            max=100,
        ),
        "max_urlscan_items": field(
            "URLScan item limit", "integer", 5, "Maximum URLs processed per email.", "MAX_URLSCAN_ITEMS", min=0, max=100
        ),
    },
    "ruleforge": {
        "max_body_mb": field(
            "Maximum request body",
            "integer",
            16,
            "Maximum Studio API body size in MB.",
            "RULEFORGE_MAX_BODY_MB",
            min=1,
            max=128,
        ),
        "max_dataset_events": field(
            "Maximum dataset events",
            "integer",
            10000,
            "Events accepted by one validation run.",
            "RULEFORGE_MAX_DATASET_EVENTS",
            min=1,
            max=1000000,
        ),
        "history_limit": field(
            "History limit",
            "integer",
            500,
            "Maximum retained rule versions.",
            "RULEFORGE_HISTORY_LIMIT",
            min=10,
            max=10000,
        ),
        "strict_refusals": field(
            "Strict translation refusals",
            "boolean",
            True,
            "Refuse lossy translations rather than weakening logic.",
            "RULEFORGE_STRICT_REFUSALS",
        ),
    },
}


class ProviderUpdate(BaseModel):
    secret: str | None = Field(default=None, max_length=4096)
    env_name: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")


class ToolSettings(BaseModel):
    values: dict[str, bool | int | float | str] = Field(default_factory=dict)


def config_path(request: Request) -> Path:
    return request.app.state.data_dir / "settings.json"


def empty() -> dict:
    return {"tools": {tool: {} for tool in TOOL_SCHEMAS}, "api_env_aliases": {}}


def load(request: Request) -> dict:
    path = config_path(request)
    if not path.is_file():
        return empty()
    try:
        return {**empty(), **json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return empty()


def save(request: Request, data: dict) -> None:
    path = config_path(request)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def defaults(tool: str) -> dict:
    return {name: definition["default"] for name, definition in TOOL_SCHEMAS[tool].items()}


def validate(tool: str, values: dict) -> dict:
    schema = TOOL_SCHEMAS[tool]
    clean = defaults(tool)
    for name, value in values.items():
        if name not in schema:
            raise HTTPException(422, detail={"code": "unknown_setting", "message": f"Unknown {tool} setting: {name}"})
        definition = schema[name]
        kind = definition["type"]
        if kind == "boolean" and not isinstance(value, bool):
            raise HTTPException(422, detail={"code": "invalid_setting", "message": f"{name} must be boolean."})
        if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise HTTPException(422, detail={"code": "invalid_setting", "message": f"{name} must be integer."})
        if kind == "integer" and not definition.get("min", value) <= value <= definition.get("max", value):
            raise HTTPException(
                422, detail={"code": "invalid_setting", "message": f"{name} is outside its allowed range."}
            )
        if kind == "string" and not isinstance(value, str):
            raise HTTPException(422, detail={"code": "invalid_setting", "message": f"{name} must be text."})
        clean[name] = value
    return clean


@router.get("")
def settings(request: Request):
    data = load(request)
    credentials = CredentialStore()
    providers = {}
    for provider, env_names in sorted(PROVIDER_ENV_KEYS.items()):
        selected = data.get("api_env_aliases", {}).get(provider) or env_names[0]
        source = credentials.source(provider, extra_env_names=(selected,))
        providers[provider] = {
            "configured": bool(source),
            "source": source or "none",
            "env_name": selected,
            "known_env_names": list(env_names),
            "tools": PROVIDER_TOOLS.get(provider, []),
            "category": "shared" if len(PROVIDER_TOOLS.get(provider, [])) > 1 else "per_tool",
        }
    return {
        "providers": providers,
        "tools": {
            tool: {"values": {**defaults(tool), **data.get("tools", {}).get(tool, {})}, "schema": schema}
            for tool, schema in TOOL_SCHEMAS.items()
        },
    }


@router.put("/tools/{tool}")
def update_tool(tool: str, body: ToolSettings, request: Request):
    if tool not in TOOL_SCHEMAS:
        raise HTTPException(404, detail={"code": "unknown_tool", "message": "Unknown tool."})
    data = load(request)
    values = validate(tool, body.values)
    data["tools"][tool] = values
    save(request, data)
    return {"tool": tool, "values": values, "restart_required": True}


@router.delete("/tools/{tool}")
def reset_tool(tool: str, request: Request):
    if tool not in TOOL_SCHEMAS:
        raise HTTPException(404, detail={"code": "unknown_tool", "message": "Unknown tool."})
    data = load(request)
    data["tools"][tool] = {}
    save(request, data)
    return {"tool": tool, "values": defaults(tool), "restart_required": True}


@router.put("/providers/{provider}")
def update_provider(provider: str, body: ProviderUpdate, request: Request):
    if provider not in PROVIDER_ENV_KEYS:
        raise HTTPException(404, detail={"code": "unknown_provider", "message": "Unknown provider."})
    data = load(request)
    if body.env_name:
        data.setdefault("api_env_aliases", {})[provider] = body.env_name
    if body.secret:
        CredentialStore().set(provider, body.secret)
    save(request, data)
    return {
        "provider": provider,
        "configured": CredentialStore().configured(provider, extra_env_names=(body.env_name,) if body.env_name else ()),
    }


@router.delete("/providers/{provider}")
def delete_provider(provider: str, request: Request):
    if provider not in PROVIDER_ENV_KEYS:
        raise HTTPException(404, detail={"code": "unknown_provider", "message": "Unknown provider."})
    CredentialStore().remove(provider)
    data = load(request)
    data.get("api_env_aliases", {}).pop(provider, None)
    save(request, data)
    return {"provider": provider, "configured": False}


def tool_environment(tool: str, values: dict) -> dict[str, str]:
    result = {}
    for name, definition in TOOL_SCHEMAS[tool].items():
        value = values.get(name, definition["default"])
        result[definition["env"]] = "true" if value is True else "false" if value is False else str(value)
    return result
