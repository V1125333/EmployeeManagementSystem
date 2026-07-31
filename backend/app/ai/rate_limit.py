"""Process-local AI limits that do not mutate HR/business database records."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Window:
    started_at: float
    count: int


_lock = threading.Lock()
_windows: dict[tuple[str, str], _Window] = {}
_active: dict[str, int] = {}


def consume_ai_rate_limit(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    now = time.monotonic()
    map_key = (scope, key)
    with _lock:
        current = _windows.get(map_key)
        if current is None or now - current.started_at >= window_seconds:
            _windows[map_key] = _Window(started_at=now, count=1)
            return True
        if current.count >= limit:
            return False
        current.count += 1
        return True


def try_acquire_ai_slot(key: str, maximum: int = 2) -> bool:
    with _lock:
        active = _active.get(key, 0)
        if active >= maximum:
            return False
        _active[key] = active + 1
        return True


def release_ai_slot(key: str) -> None:
    with _lock:
        active = _active.get(key, 0)
        if active <= 1:
            _active.pop(key, None)
        else:
            _active[key] = active - 1


def reset_ai_limits_for_tests() -> None:
    with _lock:
        _windows.clear()
        _active.clear()
