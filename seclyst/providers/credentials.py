from __future__ import annotations

import os

try:
    import keyring
except ImportError:  # Minimal runtime can continue with environment variables.
    keyring = None


PROVIDER_ENV_KEYS = {
    "virustotal": ("VT_API_KEY", "VIRUSTOTAL_API_KEY"),
    "urlscan": ("URL_SCAN_API_KEY", "URLSCAN_API_KEY"),
    "hybrid_analysis": ("HA_API_KEY", "HYBRID_ANALYSIS_API_KEY"),
    "filescan": ("FILESCAN_API_KEY",),
}


class CredentialStore:
    """Server-side credential lookup; OS keyring support can replace this backend."""

    def get(self, provider: str) -> str:
        if keyring is not None:
            try:
                value = keyring.get_password("SecLyst", provider)
                if value:
                    return value.strip()
            except Exception:
                pass
        for name in PROVIDER_ENV_KEYS.get(provider, ()):
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    def configured(self, provider: str) -> bool:
        return bool(self.get(provider))

    def set(self, provider: str, value: str) -> None:
        if keyring is None:
            raise RuntimeError("The keyring package is unavailable.")
        keyring.set_password("SecLyst", provider, value)

    def remove(self, provider: str) -> None:
        if keyring is None:
            raise RuntimeError("The keyring package is unavailable.")
        try:
            keyring.delete_password("SecLyst", provider)
        except keyring.errors.PasswordDeleteError:
            pass
