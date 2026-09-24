from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("matriva.redis")


def connect_redis() -> Any | None:
    """Connect and ping Redis when configured.

    Redis is required in production but optional for SQLite/local unit tests.  Returning
    ``None`` lets the local fallback operate while production startup can fail closed.
    """

    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return client
    except Exception as exc:
        if settings.is_production:
            raise RuntimeError("Redis connection failed") from exc
        logger.warning("Redis unavailable; continuing in local fallback mode: %s", type(exc).__name__)
        return None
