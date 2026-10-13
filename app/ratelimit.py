"""Simple in-memory sliding-window rate limiter, keyed by client IP and action.

One server instance is enough for this project, so no Redis is needed. Behind Render's proxy
uvicorn runs with --proxy-headers, which makes request.client.host the real client IP.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, limits: dict[str, tuple[int, int]], clock: Callable[[], float] = time.monotonic):
        """`limits` maps an action to (max requests, window in seconds)."""
        self._limits = limits
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, action: str, client: str) -> bool:
        max_requests, window = self._limits[action]
        now = self._clock()
        with self._lock:
            hits = self._hits[(action, client)]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= max_requests:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:
                self._drop_idle(now)
            return True

    def _drop_idle(self, now: float) -> None:
        # Keep memory bounded: forget clients whose newest request is outside every window.
        longest = max(window for _, window in self._limits.values())
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - longest]:
            del self._hits[key]
