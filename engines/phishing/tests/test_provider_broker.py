def test_vt_fetch_uses_control_plane_broker(monkeypatch):
    from core import apis

    class BrokerControl:
        enabled = True

        @staticmethod
        def provider_request(*_args, **_kwargs):
            return {
                "state": "success",
                "http_status": 200,
                "data": {"data": {"id": "example", "attributes": {}}},
                "cached": True,
            }

    monkeypatch.setattr(apis, "_provider_control", BrokerControl())
    monkeypatch.setattr(apis.requests, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("direct VT call")))
    result = apis.vt_fetch("files/" + "a" * 64)
    assert result["status"] == "ok"
    assert result["cached"] is True
    assert result["json"]["data"]["id"] == "example"
