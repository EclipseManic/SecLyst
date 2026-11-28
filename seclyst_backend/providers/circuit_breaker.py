from __future__ import annotations

import threading
import time


class CircuitBreaker:
    def __init__(self) -> None:
        self._state: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def allow(self, provider: str) -> bool:
        with self._lock:
            failures, open_until = self._state.get(provider, (0, 0.0))
            return not (failures and open_until > time.monotonic())

    def success(self, provider: str) -> None:
        with self._lock:
            self._state[provider] = (0, 0.0)

    def failure(self, provider: str, threshold: int, cooldown_seconds: int) -> None:
        with self._lock:
            failures, _open_until = self._state.get(provider, (0, 0.0))
            failures += 1
            open_until = time.monotonic() + cooldown_seconds if failures >= threshold else 0.0
            self._state[provider] = (failures, open_until)
