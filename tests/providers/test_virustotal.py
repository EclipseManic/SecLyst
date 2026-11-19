import httpx

from seclyst.providers.adapters.virustotal import VirusTotalAdapter


def adapter_for(handler) -> VirusTotalAdapter:
    client = httpx.Client(
        base_url="https://www.virustotal.com/api/v3",
        transport=httpx.MockTransport(handler),
    )
    return VirusTotalAdapter(client=client)


def test_virustotal_adapter_returns_raw_success_payload() -> None:
    adapter = adapter_for(lambda request: httpx.Response(200, json={"data": {"id": "abc"}}, request=request))
    result = adapter.lookup("sha256", "a" * 64, {}, "secret")
    assert result == {"state": "success", "http_status": 200, "data": {"data": {"id": "abc"}}}


def test_virustotal_adapter_preserves_retry_after() -> None:
    adapter = adapter_for(lambda request: httpx.Response(429, headers={"Retry-After": "17"}, request=request))
    result = adapter.lookup("domain", "example.test", {}, "secret")
    assert result["state"] == "waiting_rate_limit"
    assert result["retry_after"] == 17


def test_virustotal_adapter_rejects_arbitrary_paths_without_network() -> None:
    adapter = adapter_for(lambda _request: (_ for _ in ()).throw(AssertionError("network request")))
    result = adapter.lookup("path", "ignored", {"path": "../users"}, "secret")
    assert result["state"] == "invalid_request"
