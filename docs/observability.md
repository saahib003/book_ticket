# Observability

Observability means being able to explain what the system is doing from
external evidence. Logs describe individual events; metrics aggregate behavior
over time; traces (not yet implemented) follow one request across components.

This project currently exposes Prometheus metrics at `/metrics`:

- `ticket_booking_http_requests_total`: request count by method, endpoint, and
  status code.
- `ticket_booking_http_request_duration_seconds`: latency histogram by method
  and endpoint.
- `ticket_booking_cache_operations_total`: cache hits, misses, successes, and
  errors by operation.

The request middleware starts a timer before dispatch and records the result
after the response. Cache helpers record outcomes without allowing metrics
failure to change booking behavior. Prometheus is a monitoring library, not a
database; metrics are for diagnosis and trend analysis, while PostgreSQL
remains the business source of truth.

Inspect metrics locally:

```powershell
cd backend
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:5000/metrics` while Locust is running. Compare request
histograms and cache hit/miss counts with Locust's p50/p95/p99 report. Never
expose this endpoint publicly without authentication or network restriction.
