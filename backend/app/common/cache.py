"""Cache-aside helpers. Cache data is display-only and may be stale briefly."""

import json

from flask import current_app

from app.common.metrics import CACHE_OPERATIONS


def cache_get(key: str):
    try:
        value = current_app.extensions["redis"].get(key)
        CACHE_OPERATIONS.labels("get", "hit" if value else "miss").inc()
        return json.loads(value) if value else None
    except Exception:
        CACHE_OPERATIONS.labels("get", "error").inc()
        current_app.logger.warning("Cache read failed for %s", key)
        return None


def cache_set(key: str, value, ttl_seconds: int) -> None:
    try:
        current_app.extensions["redis"].setex(key, ttl_seconds, json.dumps(value))
        CACHE_OPERATIONS.labels("set", "success").inc()
    except Exception:
        CACHE_OPERATIONS.labels("set", "error").inc()
        current_app.logger.warning("Cache write failed for %s", key)


def cache_delete(*keys: str) -> None:
    if not keys:
        return
    try:
        current_app.extensions["redis"].delete(*keys)
        CACHE_OPERATIONS.labels("delete", "success").inc()
    except Exception:
        CACHE_OPERATIONS.labels("delete", "error").inc()
        current_app.logger.warning("Cache invalidation failed for %s", keys)


def cache_delete_pattern(pattern: str) -> None:
    """Best-effort invalidation for related cache-aside keys."""
    try:
        client = current_app.extensions["redis"]
        keys = list(client.scan_iter(match=pattern))
        if keys:
            client.delete(*keys)
        CACHE_OPERATIONS.labels("delete_pattern", "success").inc()
    except Exception:
        CACHE_OPERATIONS.labels("delete_pattern", "error").inc()
        current_app.logger.warning("Cache pattern invalidation failed for %s", pattern)
