"""Lightweight in-memory rate limiting.

Suitable for a single-process deployment (this ERP runs one uvicorn worker on
the hospital LAN). Two mechanisms:

* :func:`check_rate` — sliding-window counter (e.g. public booking endpoint).
* :class:`LoginGuard` — failed-login lockout per (username, ip).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.config import get_settings
from app.exceptions import RateLimitError

settings = get_settings()

_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate(key: str, limit: int, per_seconds: int) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    now = time.monotonic()
    q = _windows[key]
    while q and now - q[0] > per_seconds:
        q.popleft()
    if len(q) >= limit:
        raise RateLimitError("Too many requests — please wait a moment and try again.")
    q.append(now)


class LoginGuard:
    MAX_FAILS = 5
    LOCK_SECONDS = 300

    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = defaultdict(list)

    def assert_not_locked(self, key: str) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        now = time.monotonic()
        fails = [t for t in self._fails[key] if now - t < self.LOCK_SECONDS]
        self._fails[key] = fails
        if len(fails) >= self.MAX_FAILS:
            raise RateLimitError(
                "Account temporarily locked after repeated failed sign-ins. "
                "Try again in a few minutes.")

    def record_failure(self, key: str) -> None:
        self._fails[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


login_guard = LoginGuard()
