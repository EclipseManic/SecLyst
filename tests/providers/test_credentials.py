from seclyst_backend.providers import credentials


def test_environment_credential_fallback(monkeypatch) -> None:
    monkeypatch.setattr(credentials, "keyring", None)
    monkeypatch.setenv("VT_API_KEY", "environment-secret")
    assert credentials.CredentialStore().get("virustotal") == "environment-secret"
    assert credentials.CredentialStore().configured("virustotal") is True
