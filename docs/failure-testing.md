# Failure testing

Run the unit failure checks:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Expected result currently: `22 passed`.

Covered failures include invalid credentials, rate limiting, Redis failure
during a hold, partial multi-seat conflicts, duplicate webhook delivery,
expired holds, failed payments, and cancellation rules.

Manual dependency experiment:

```powershell
docker stop ticket-booking-redis
```

While Redis is stopped, `/health/ready` should return `503`, but a valid
PostgreSQL-backed hold must not create a second owner for a seat. Restart it:

```powershell
docker start ticket-booking-redis
```

Redis clients use bounded quarter-second connect and read timeouts. Therefore
cache-backed catalogue requests should fall back to PostgreSQL promptly rather
than waiting indefinitely for a dead Redis socket. Readiness still reports
`503` because Redis is required for the complete local runtime.

PostgreSQL connections use a bounded one-second connect timeout, connection
pool pre-pinging, and a bounded pool wait. Liveness remains available because
it checks only the application process. A controlled local outage still
returns a consistent `503 DEPENDENCY_UNAVAILABLE` response at the API boundary;
the regression test covers this mapping. The driver-level connection timeout
still controls how quickly a live request reaches that boundary.

Do not run this experiment while another learner is using the shared local
environment. It intentionally changes dependency availability.
