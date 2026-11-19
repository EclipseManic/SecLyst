from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from .policies import ProviderPolicyValue


@dataclass
class WindowState:
    minute_calls: deque[float]
    day_calls: deque[float]
    cooldown_until: float = 0.0


class ProviderScheduler:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], WindowState] = {}
        self._semaphores: dict[tuple[str, str], threading.BoundedSemaphore] = {}
        self._lock = threading.Lock()

    def acquire(self, provider: str, operation: str, policy: ProviderPolicyValue) -> tuple[bool, float]:
        key = (provider, operation)
        now = time.monotonic()
        with self._lock:
            state = self._states.setdefault(key, WindowState(deque(), deque()))
            while state.minute_calls and state.minute_calls[0] <= now - 60:
                state.minute_calls.popleft()
            while state.day_calls and state.day_calls[0] <= now - 86400:
                state.day_calls.popleft()
            retry_after = max(0.0, state.cooldown_until - now)
            if retry_after:
                return False, retry_after
            if len(state.minute_calls) >= policy.requests_per_minute:
                return False, max(0.1, 60 - (now - state.minute_calls[0]))
            if len(state.day_calls) >= policy.requests_per_day:
                return False, max(0.1, 86400 - (now - state.day_calls[0]))
            semaphore = self._semaphores.setdefault(key, threading.BoundedSemaphore(policy.max_concurrency))
            if not semaphore.acquire(blocking=False):
                return False, 0.25
            state.minute_calls.append(now)
            state.day_calls.append(now)
            return True, 0.0

    def release(self, provider: str, operation: str) -> None:
        semaphore = self._semaphores.get((provider, operation))
        if semaphore:
            semaphore.release()

    def cooldown(self, provider: str, operation: str, seconds: float) -> None:
        with self._lock:
            state = self._states.setdefault((provider, operation), WindowState(deque(), deque()))
            state.cooldown_until = max(state.cooldown_until, time.monotonic() + max(0.0, seconds))
