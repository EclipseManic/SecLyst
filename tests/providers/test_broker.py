from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from seclyst_backend.database.models import ProviderRequest
from seclyst_backend.database.session import Database
from seclyst_backend.providers.broker import ProviderBroker, ProviderRequestCommand
from seclyst_backend.providers.policies import ProviderPolicyValue


class Credentials:
    def __init__(self, value: str = "test-key") -> None:
        self.value = value

    def get(self, _provider: str) -> str:
        return self.value


class FakeAdapter:
    provider = "virustotal"
    version = "test-v1"

    def __init__(self, state: str = "success", delay: float = 0) -> None:
        self.state = state
        self.delay = delay
        self.calls = 0
        self.lock = threading.Lock()

    def lookup(self, subject_type, subject, options, credential):
        with self.lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        return {
            "state": self.state,
            "http_status": 200 if self.state == "success" else 404 if self.state == "not_found" else 503,
            "data": {"subject": subject, "type": subject_type, "credential": bool(credential), "options": options},
        }


def broker(tmp_path, adapter: FakeAdapter, *, credential: str = "test-key") -> tuple[ProviderBroker, Database]:
    database = Database(tmp_path / "provider.db", create_schema=True)
    service = ProviderBroker(database, credentials=Credentials(credential))
    service.register(adapter)
    service.set_policy("virustotal", "lookup", ProviderPolicyValue(
        requests_per_minute=100,
        requests_per_day=1000,
        max_concurrency=10,
        positive_ttl_seconds=60,
        negative_ttl_seconds=10,
    ))
    return service, database


def command(subject: str = "a" * 64) -> ProviderRequestCommand:
    return ProviderRequestCommand("virustotal", "lookup", "sha256", subject)


def test_success_is_cached_with_provenance(tmp_path) -> None:
    adapter = FakeAdapter()
    service, database = broker(tmp_path, adapter)
    try:
        first = service.request(command())
        second = service.request(command())
        assert first.state == second.state == "success"
        assert first.cached is False
        assert second.cached is True
        assert second.cache_key == first.cache_key
        assert adapter.calls == 1
    finally:
        database.dispose()


def test_identical_concurrent_calls_use_single_flight(tmp_path) -> None:
    adapter = FakeAdapter(delay=0.1)
    service, database = broker(tmp_path, adapter)
    try:
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(lambda _index: service.request(command()), range(12)))
        assert {result.state for result in results} == {"success"}
        assert adapter.calls == 1
    finally:
        database.dispose()


def test_no_credential_never_calls_provider(tmp_path) -> None:
    adapter = FakeAdapter()
    service, database = broker(tmp_path, adapter, credential="")
    try:
        result = service.request(command())
        assert result.state == "no_credential"
        assert adapter.calls == 0
    finally:
        database.dispose()


def test_provider_failures_are_not_cached(tmp_path) -> None:
    adapter = FakeAdapter(state="unavailable")
    service, database = broker(tmp_path, adapter)
    try:
        assert service.request(command()).state == "unavailable"
        assert service.request(command()).state == "unavailable"
        assert adapter.calls == 2
    finally:
        database.dispose()


def test_global_rate_policy_waits_instead_of_calling(tmp_path) -> None:
    adapter = FakeAdapter()
    service, database = broker(tmp_path, adapter)
    service.set_policy("virustotal", "lookup", ProviderPolicyValue(
        requests_per_minute=1,
        requests_per_day=100,
        max_concurrency=1,
    ))
    try:
        assert service.request(command("a" * 64)).state == "success"
        waiting = service.request(command("b" * 64))
        assert waiting.state == "waiting_rate_limit"
        assert waiting.retry_after and waiting.retry_after > 0
        assert adapter.calls == 1
    finally:
        database.dispose()


def test_request_audit_rows_are_persisted(tmp_path) -> None:
    adapter = FakeAdapter()
    service, database = broker(tmp_path, adapter)
    try:
        service.request(command())
        with database.session() as session:
            rows = session.query(ProviderRequest).all()
        assert len(rows) == 1
        assert rows[0].status == "success"
        assert rows[0].input_hash != "a" * 64
    finally:
        database.dispose()
