import json
import logging
import time
import uuid
from collections import Counter, defaultdict
from contextvars import ContextVar
from typing import Any

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("matriva.api")


def new_request_id() -> str:
    return uuid.uuid4().hex


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    """Emit structured metadata without logging request bodies or health data."""

    safe_fields = {
        key: value
        for key, value in fields.items()
        if key not in {"message", "query", "answer", "profile", "health", "token", "password"}
    }
    logger.info("%s %s", event, json.dumps(safe_fields, default=str, separators=(",", ":")))


class Metrics:
    def __init__(self) -> None:
        self._lock: Counter[tuple[str, int]] = Counter()
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self.started_at = time.time()

    def observe(self, route: str, latency_ms: float, status_code: int) -> None:
        self._lock[(route, status_code)] += 1
        values = self._latencies[route]
        values.append(latency_ms)
        if len(values) > 1000:
            del values[: len(values) - 1000]

    def snapshot(self) -> dict[str, Any]:
        return {
            "uptime_seconds": round(time.time() - self.started_at, 3),
            "requests": {f"{route}:{status}": count for (route, status), count in self._lock.items()},
            "latency_ms": {
                route: {
                    "count": len(values),
                    "average": round(sum(values) / len(values), 2),
                    "max": round(max(values), 2),
                }
                for route, values in self._latencies.items()
            },
        }


metrics = Metrics()
