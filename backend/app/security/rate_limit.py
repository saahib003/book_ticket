"""Small Redis-backed fixed-window rate limiter for local learning."""

from functools import wraps

from flask import current_app, jsonify, request


def enforce_rate_limit(name: str, limit: int, window_seconds: int, identity: str | None = None):
    """Return a response when the caller exceeds a window, otherwise None."""
    client = current_app.extensions["redis"]
    key_identity = identity or request.remote_addr or "unknown"
    key = f"rate:{name}:{key_identity}"
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)
        if count > limit:
            return jsonify({"error": {"code": "RATE_LIMITED", "message": "Too many requests. Try again later."}}), 429
    except Exception:
        # Rate limiting is a guardrail, not a correctness dependency. A Redis
        # outage must not turn a valid PostgreSQL seat transaction into a lie.
        current_app.logger.warning("Rate limiter unavailable for %s", name)
    return None


def rate_limit(name: str, limit: int, window_seconds: int):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            blocked = enforce_rate_limit(name, limit, window_seconds)
            return blocked or function(*args, **kwargs)

        return wrapped
    return decorator

