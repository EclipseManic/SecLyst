"""Single-user authentication for the SecLyst control plane.

SecLyst is a loopback-only workbench for one analyst, so this is deliberately
not a multi-tenant account system. It closes the one real gap: the shell used to
open for anyone who could reach the port, and its account popover said so
("This session, not authenticated").

The browser access token in :mod:`seclyst_backend.server` isolates hosted tool frames
from the shell. That is transport isolation, not identity. This module adds the
missing identity: a single password, stored only as a salted scrypt hash, a
short-lived server-side session, and an HttpOnly cookie that gates the
control-plane API.

Design notes:

* The password hash lives under the data directory (``auth.json``) with the
  owning user's read/write bits only where the platform allows it. Nothing is
  written to the database, so a copied database cannot leak the credential.
* Sessions are held in memory and expire. Restarting SecLyst signs everyone out;
  that is intended, not a limitation.
* Verification is constant-time and the file format is versioned so the hash
  parameters can move later without breaking an existing install.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

PASSWORD_FILE = "auth.json"
SESSION_COOKIE = "seclyst_session"

# scrypt at ~16 MiB is a deliberate cost for the one interactive login a person
# performs; it is far below the point where a laptop login feels slow.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32
_SALT_LEN = 16
_MIN_PASSWORD_LENGTH = 12


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_KEY_LEN)


class PasswordStore:
    """One salted scrypt hash persisted under the data directory."""

    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / PASSWORD_FILE

    def configured(self) -> bool:
        return self.path.is_file()

    def set(self, password: str) -> None:
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")
        salt = secrets.token_bytes(_SALT_LEN)
        digest = _derive(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
        payload = {
            "version": 1,
            "algorithm": "scrypt",
            "n": _SCRYPT_N,
            "r": _SCRYPT_R,
            "p": _SCRYPT_P,
            "salt": salt.hex(),
            "hash": digest.hex(),
            "updated_at": int(time.time()),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            # Windows and some mounts do not map POSIX mode bits; the file still
            # lives inside the user's own data directory.
            pass

    def verify(self, password: str) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            salt = bytes.fromhex(payload["salt"])
            expected = bytes.fromhex(payload["hash"])
            n = int(payload.get("n", _SCRYPT_N))
            r = int(payload.get("r", _SCRYPT_R))
            p = int(payload.get("p", _SCRYPT_P))
        except (OSError, ValueError, KeyError, TypeError):
            return False
        digest = _derive(password, salt, n, r, p)
        return hmac.compare_digest(digest, expected)


class SessionManager:
    """In-memory, expiring sessions. A process restart invalidates all of them."""

    def __init__(self, ttl_seconds: int = 8 * 60 * 60) -> None:
        self.ttl = max(60, int(ttl_seconds))
        self._sessions: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        sid = secrets.token_urlsafe(32)
        with self._lock:
            self._sweep_locked()
            self._sessions[sid] = time.time() + self.ttl
        return sid

    def valid(self, sid: str | None) -> bool:
        if not sid:
            return False
        with self._lock:
            expiry = self._sessions.get(sid)
            if expiry is None:
                return False
            if expiry <= time.time():
                self._sessions.pop(sid, None)
                return False
            return True

    def revoke(self, sid: str | None) -> None:
        if not sid:
            return
        with self._lock:
            self._sessions.pop(sid, None)

    def revoke_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _sweep_locked(self) -> None:
        now = time.time()
        for sid in [key for key, expiry in self._sessions.items() if expiry <= now]:
            self._sessions.pop(sid, None)


class AuthService:
    """Password gate and session issuer for the single local analyst."""

    def __init__(
        self,
        data_dir: Path,
        *,
        enabled: bool = True,
        session_ttl_seconds: int = 8 * 60 * 60,
    ) -> None:
        self.enabled = enabled
        self.passwords = PasswordStore(data_dir)
        self.sessions = SessionManager(session_ttl_seconds)

    @property
    def configured(self) -> bool:
        return self.passwords.configured()

    @property
    def cookie_max_age(self) -> int:
        return self.sessions.ttl

    def status(self, sid: str | None) -> dict[str, Any]:
        return {
            "required": self.enabled,
            "configured": self.configured,
            "authenticated": (not self.enabled) or self.sessions.valid(sid),
        }

    def login(self, password: str) -> str | None:
        """Return a fresh session id when the password matches, else ``None``."""
        if not self.configured or not self.passwords.verify(password):
            return None
        return self.sessions.create()

    def set_password(self, password: str) -> str:
        """Set or replace the password and return a fresh session id."""
        self.passwords.set(password)
        return self.sessions.create()
