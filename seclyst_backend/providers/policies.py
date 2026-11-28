from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPolicyValue:
    requests_per_minute: int = 4
    requests_per_day: int = 500
    max_concurrency: int = 2
    timeout_seconds: int = 15
    max_safe_retries: int = 1
    positive_ttl_seconds: int = 21600
    negative_ttl_seconds: int = 900
    stale_seconds: int = 3600
    circuit_failures: int = 5
    circuit_cooldown_seconds: int = 60


DEFAULT_POLICIES = {
    ("virustotal", "lookup"): ProviderPolicyValue(),
}
