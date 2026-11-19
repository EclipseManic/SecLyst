from run import app


def test_seclyst_health_contract() -> None:
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"engine": "phishing", "status": "ok"}
