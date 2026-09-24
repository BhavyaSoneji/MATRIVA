from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """Small process-local limiter with a Redis-compatible interface boundary.

    The limiter is deliberately dependency-free for local development.  A multi-worker
    deployment should replace the storage with Redis using the same allow/reset methods.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])) + 1)
                return False, 0, retry_after
            events.append(now)
            if len(self._events) > 10_000:
                stale_keys = [key for key, values in self._events.items() if not values or values[-1] < cutoff]
                for stale_key in stale_keys:
                    self._events.pop(stale_key, None)
            return True, max(0, limit - len(events)), 0

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = InMemoryRateLimiter()
