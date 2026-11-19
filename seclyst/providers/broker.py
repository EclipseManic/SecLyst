from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from ..cache.keys import provider_cache_key
from ..cache.store import CacheStore
from ..database.models import ProviderRequest
from ..database.session import Database
from .circuit_breaker import CircuitBreaker
from .credentials import CredentialStore
from .policies import DEFAULT_POLICIES, ProviderPolicyValue
from .scheduler import ProviderScheduler


class ProviderAdapter(Protocol):
    provider: str
    version: str

    def lookup(self, subject_type: str, subject: str, options: dict[str, Any], credential: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ProviderRequestCommand:
    provider: str
    operation: str
    subject_type: str
    subject: str
    options: dict[str, Any] = field(default_factory=dict)
    force_refresh: bool = False


@dataclass(frozen=True)
class ProviderResult:
    state: str
    data: Any = None
    http_status: int | None = None
    retry_after: int | None = None
    cached: bool = False
    stale: bool = False
    cache_key: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "data": self.data,
            "http_status": self.http_status,
            "retry_after": self.retry_after,
            "cached": self.cached,
            "stale": self.stale,
            "cache_key": self.cache_key,
            "error": self.error,
        }


@dataclass
class _Flight:
    event: threading.Event = field(default_factory=threading.Event)
    result: ProviderResult | None = None


class ProviderBroker:
    def __init__(
        self,
        database: Database,
        *,
        credentials: CredentialStore | None = None,
        scheduler: ProviderScheduler | None = None,
    ) -> None:
        self.database = database
        self.credentials = credentials or CredentialStore()
        self.scheduler = scheduler or ProviderScheduler()
        self.cache = CacheStore(database)
        self.circuit = CircuitBreaker()
        self.adapters: dict[str, ProviderAdapter] = {}
        self.policies = dict(DEFAULT_POLICIES)
        self._flights: dict[str, _Flight] = {}
        self._lock = threading.Lock()

    def register(self, adapter: ProviderAdapter) -> None:
        self.adapters[adapter.provider] = adapter

    def set_policy(self, provider: str, operation: str, policy: ProviderPolicyValue) -> None:
        self.policies[(provider, operation)] = policy

    def request(self, command: ProviderRequestCommand) -> ProviderResult:
        adapter = self.adapters.get(command.provider)
        if adapter is None or command.operation != "lookup":
            return ProviderResult("invalid_request", error="Provider operation is not registered.")
        key = provider_cache_key(
            command.provider,
            command.operation,
            command.subject_type,
            command.subject,
            command.options,
        )
        if not command.force_refresh:
            cached = self.cache.get(key)
            if cached:
                value = cached.value
                return ProviderResult(
                    state=value["state"],
                    data=value.get("data"),
                    http_status=value.get("http_status"),
                    retry_after=value.get("retry_after"),
                    cached=True,
                    stale=cached.stale,
                    cache_key=key,
                    error=value.get("error"),
                )

        credential = self.credentials.get(command.provider)
        if not credential:
            return ProviderResult("no_credential", error=f"{command.provider} credential is not configured.")
        if not self.circuit.allow(command.provider):
            return ProviderResult("unavailable", error="Provider circuit breaker is open.")

        with self._lock:
            flight = self._flights.get(key)
            if flight is None:
                flight = _Flight()
                self._flights[key] = flight
                leader = True
            else:
                leader = False
        if not leader:
            flight.event.wait(timeout=30)
            return flight.result or ProviderResult("timeout", error="Single-flight provider request timed out.")

        try:
            result = self._execute(command, adapter, credential, key)
            flight.result = result
            return result
        finally:
            flight.event.set()
            with self._lock:
                self._flights.pop(key, None)

    def _execute(
        self,
        command: ProviderRequestCommand,
        adapter: ProviderAdapter,
        credential: str,
        cache_key: str,
    ) -> ProviderResult:
        policy = self.policies.get((command.provider, command.operation), ProviderPolicyValue())
        acquired, retry_after = self.scheduler.acquire(command.provider, command.operation, policy)
        if not acquired:
            return ProviderResult("waiting_rate_limit", retry_after=max(1, int(retry_after)), cache_key=cache_key)

        request_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        row = ProviderRequest(
            id=request_id,
            request_key=cache_key,
            provider=command.provider,
            operation=command.operation,
            status="running",
            input_hash=hashlib.sha256(command.subject.encode()).hexdigest(),
            started_at=now,
        )
        with self.database.session() as session, session.begin():
            session.add(row)
        try:
            raw = adapter.lookup(command.subject_type, command.subject, command.options, credential)
            result = ProviderResult(
                state=raw.get("state", "provider_error"),
                data=raw.get("data"),
                http_status=raw.get("http_status"),
                retry_after=raw.get("retry_after"),
                cached=False,
                cache_key=cache_key,
                error=raw.get("error"),
            )
            if result.state == "waiting_rate_limit":
                self.scheduler.cooldown(command.provider, command.operation, result.retry_after or 60)
            if result.state in {"success", "not_found"}:
                ttl = policy.positive_ttl_seconds if result.state == "success" else policy.negative_ttl_seconds
                self.cache.put(
                    cache_key,
                    result.as_dict(),
                    producer=command.provider,
                    producer_version=adapter.version,
                    ttl_seconds=ttl,
                    stale_seconds=policy.stale_seconds,
                )
                self.circuit.success(command.provider)
            elif result.state in {"unavailable", "timeout", "provider_error"}:
                self.circuit.failure(command.provider, policy.circuit_failures, policy.circuit_cooldown_seconds)
            self._finish_request(request_id, result)
            return result
        except Exception as exc:
            self.circuit.failure(command.provider, policy.circuit_failures, policy.circuit_cooldown_seconds)
            result = ProviderResult("provider_error", error=str(exc)[:500], cache_key=cache_key)
            self._finish_request(request_id, result)
            return result
        finally:
            self.scheduler.release(command.provider, command.operation)

    def _finish_request(self, request_id: str, result: ProviderResult) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(ProviderRequest, request_id)
            if row:
                row.status = result.state
                row.finished_at = datetime.now(UTC)
                row.http_status = result.http_status
                row.cache_entry_key = result.cache_key if result.state in {"success", "not_found"} else None
                row.error_code = result.state if result.error else None
                if result.retry_after:
                    row.retry_after = datetime.now(UTC) + timedelta(seconds=result.retry_after)
