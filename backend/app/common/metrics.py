"""Small Prometheus metrics shared by request and cache instrumentation."""

from prometheus_client import Counter, Histogram, generate_latest


REQUESTS = Counter(
    "ticket_booking_http_requests_total",
    "HTTP requests handled by the API.",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "ticket_booking_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "endpoint"],
)
CACHE_OPERATIONS = Counter(
    "ticket_booking_cache_operations_total",
    "Cache operations grouped by operation and outcome.",
    ["operation", "outcome"],
)


def metrics_payload() -> bytes:
    """Return the standard Prometheus text exposition format."""
    return generate_latest()
