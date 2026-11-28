from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def provider_cache_key(provider: str, operation: str, subject_type: str, subject: str, options: dict[str, Any]) -> str:
    payload = [provider, operation, subject_type, subject.strip().lower(), options]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
