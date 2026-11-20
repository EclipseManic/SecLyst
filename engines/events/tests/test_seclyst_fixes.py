from app.ioc_extractor import extract_iocs
from app import report_generator


def test_ioc_extractor_prefers_complete_url_and_email_tokens():
    items = extract_iocs({"description": "Visit https://evil.example/path and email attacker@evil.example"})
    values = {(item["ioc_type"], item["value"]) for item in items}
    assert ("url", "https://evil.example/path") in values
    assert ("email", "attacker@evil.example") in values
    assert ("domain", "evil.example") not in values


def test_report_status_interpolates_authoritative_event_total(monkeypatch):
    monkeypatch.setattr(report_generator.db, "get_investigation", lambda _id: {"name": "Test"})
    monkeypatch.setattr(report_generator.db, "get_events", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(report_generator.db, "get_event_count", lambda _id: 12345)
    monkeypatch.setattr(report_generator.db, "get_ioc_summary", lambda _id: {"types": {}, "total": 77})
    monkeypatch.setattr(report_generator.db, "count_sigma_matches", lambda _id: 11)
    monkeypatch.setattr(report_generator.db, "get_channels", lambda _id: ["Security"])
    monkeypatch.setattr(report_generator.db, "get_providers", lambda _id: ["Microsoft"])
    report = report_generator.generate_report("investigation")
    assert "<div class=\"card-value\">12345</div>" in report
    assert "<div class=\"card-value\">77</div>" in report
    assert "<div class=\"card-value\">11</div>" in report
    assert "Events: 12345 | Channels: 1 | Providers: 1" in report
    assert "{total_count}" not in report
