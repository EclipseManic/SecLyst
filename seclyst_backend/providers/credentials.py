from __future__ import annotations

import os
import json
from pathlib import Path

try:
    import keyring
except ImportError:  # Minimal runtime can continue with environment variables.
    keyring = None


PROVIDER_ENV_KEYS = {
    "virustotal": ("VT_API_KEY", "VIRUSTOTAL_API_KEY"),
    "urlscan": ("URL_SCAN_API_KEY", "URLSCAN_API_KEY"),
    "hybrid_analysis": ("HA_API_KEY", "HYBRID_ANALYSIS_API_KEY"),
    "filescan": ("FILESCAN_API_KEY",),
    "abuseipdb": ("ABUSEIPDB_API_KEY",),
    "shodan": ("SHODAN_API_KEY",),
    "otx": ("OTX_API_KEY",),
    "greynoise": ("GREYNOISE_API_KEY",),
    "censys": ("CENSYS_API_KEY",),
    "ipinfo": ("IPINFO_API_KEY",),
    "nvd": ("NVD_API_KEY",),
    "etherscan": ("ETHERSCAN_API_KEY",),
    "abstractapi": ("ABSTRACTAPI_KEY",),
    "ipqualityscore": ("IPQUALITYSCORE_API_KEY",),
    "hunter": ("HUNTER_API_KEY",),
    "malwarebazaar": ("MB_AUTH_KEY", "ABUSH_CH_AUTH_KEY", "ABUSE_CH_AUTH_KEY", "ABUSE_CH_API_KEY", "ABUSECH_API_KEY"),
    "threatfox": ("THREATFOX_API_KEY", "MB_AUTH_KEY", "ABUSH_CH_AUTH_KEY", "ABUSE_CH_API_KEY"),
    "urlhaus": ("URLHAUS_API_KEY", "MB_AUTH_KEY", "ABUSH_CH_AUTH_KEY", "ABUSE_CH_API_KEY"),
    "triage": ("TRIAGE_API_KEY", "TRIA_GE_API_KEY"),
    "chainabuse": ("CHAINABUSE_API_KEY", "CHAINABUSE_API", "CHAIN_BUSE_API"),
    "hudson_rock": ("HUDSON_API_KEY", "HUDSON_ROCK_API_KEY", "HUDSONROCK_API_KEY"),
}


class CredentialStore:
    """Server-side credential lookup; OS keyring support can replace this backend."""

    def get(self, provider: str, *, extra_env_names: tuple[str, ...] = ()) -> str:
        configured_alias = self._configured_alias(provider)
        if configured_alias:
            extra_env_names = (configured_alias, *extra_env_names)
        if keyring is not None:
            try:
                value = keyring.get_password("SecLyst", provider)
                if value:
                    return value.strip()
            except Exception:
                pass
        for name in (*extra_env_names, *PROVIDER_ENV_KEYS.get(provider, ())):
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    def configured(self, provider: str, *, extra_env_names: tuple[str, ...] = ()) -> bool:
        return bool(self.get(provider, extra_env_names=extra_env_names))

    def source(self, provider: str, *, extra_env_names: tuple[str, ...] = ()) -> str | None:
        configured_alias = self._configured_alias(provider)
        if configured_alias:
            extra_env_names = (configured_alias, *extra_env_names)
        if keyring is not None:
            try:
                if keyring.get_password("SecLyst", provider):
                    return "keyring"
            except Exception:
                pass
        for name in (*extra_env_names, *PROVIDER_ENV_KEYS.get(provider, ())):
            if os.getenv(name, "").strip():
                return f"environment:{name}"
        return None

    @staticmethod
    def _configured_alias(provider: str) -> str | None:
        path_value = os.getenv("SECLYST_SETTINGS_PATH", "").strip()
        if not path_value:
            return None
        try:
            data = json.loads(Path(path_value).read_text(encoding="utf-8"))
            value = data.get("api_env_aliases", {}).get(provider)
            return value if isinstance(value, str) and value else None
        except (OSError, json.JSONDecodeError):
            return None

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
