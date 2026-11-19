import pytest

from app.backend.adapters.virus_total import VirusTotalAdapter


@pytest.mark.asyncio
async def test_virustotal_adapter_uses_control_plane_broker(monkeypatch):
    adapter = VirusTotalAdapter()

    class BrokerControl:
        enabled = True

        @staticmethod
        def provider_request(*_args, **_kwargs):
            return {
                "state": "success",
                "http_status": 200,
                "data": {
                    "data": {
                        "id": "a" * 64,
                        "attributes": {
                            "last_analysis_stats": {
                                "malicious": 2,
                                "suspicious": 0,
                                "harmless": 8,
                                "undetected": 0,
                            }
                        },
                    }
                },
                "cached": True,
            }

    adapter.provider_control = BrokerControl()
    monkeypatch.setattr(adapter, "_get_client", lambda: (_ for _ in ()).throw(AssertionError("direct VT client")))
    result = await adapter.lookup("a" * 64, "sha256")
    assert result.execution_state == "success"
    assert result.detection_count == 2
    assert result.total_engines == 10
