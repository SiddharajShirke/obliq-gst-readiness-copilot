from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class InProcessRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        """Clear process-local counters for an isolated runtime or test boundary."""

        with self._lock:
            self._events.clear()


rate_limiter = InProcessRateLimiter()
