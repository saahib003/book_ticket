# Load and failure testing

Milestone 9 uses two complementary experiments:

- `backend/scripts/concurrency_hold_test.py` sends 100 concurrent attempts for
  one seat. Correctness requires exactly one `201`, 99 expected `409` conflicts,
  and no unexpected responses.
- `load-tests/locustfile.py` exercises browse, seat-map reads, holds, and the
  booking/payment confirmation path. Locust records response latency and
  reports p50, p95, and p99 values.

## Install and run a local load test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[load]"
cd ..
..\backend\.venv\Scripts\python.exe -m locust -f load-tests\locustfile.py --headless -u 5 -r 1 -t 60s --host http://127.0.0.1:5000
```

Use a small user count locally. The booking task intentionally changes
database state by consuming seats; use a dedicated seeded show or resettable
test database. The Locust summary includes request count, failures, average,
median (p50), p95, and p99 latency.

## Controlled dependency experiments

Stop and restart one dependency at a time, recording readiness, request
status, and recovery time:

```powershell
docker stop ticket-booking-redis
# check /health/ready and exercise a PostgreSQL-backed hold
docker start ticket-booking-redis

docker stop ticket-booking-postgres
# check /health/ready; do not issue booking writes during this interval
docker start ticket-booking-postgres
```

Redis outage may remove cache, TTL, rate-limit, and realtime coordination, but
must not create a second seat owner. PostgreSQL outage must fail closed for
authoritative writes. Celery outage leaves committed outbox work pending; a
worker restart must process it exactly once into notifications.

## Evidence table

Record each run with the date, users, spawn rate, duration, database pool
size, worker count, cache state, p50/p95/p99, error rate, and observations.
This makes later comparisons of indexes, caching, and worker counts
reproducible instead of anecdotal.

During a running local API, inspect `http://127.0.0.1:5000/metrics`. The
Prometheus text output includes request totals by method/endpoint/status,
request-duration histograms, and cache operation outcomes. Cache hits and
misses explain why a seat or catalogue request may change latency; they should
be recorded beside Locust percentiles. The endpoint is intentionally local and
must be protected or restricted before production exposure.

## Baseline run: 2026-09-02

The first controlled run used three users, a one-user/second ramp, and a
20-second duration. It produced 107 requests. Its aggregate approximate
latency was p50 11 ms, p95 47 ms, and p99 74 ms. The apparent 22.43% failure
rate was entirely expected `409 SEATS_UNAVAILABLE` contention, which exposed
that the initial harness needed business-outcome classification.

After correcting the harness, a three-user, one-user/second, 10-second run
produced 49 requests with 0% measured failures: p50 6 ms, p95 74 ms, and p99
150 ms. It mostly measured catalogue, seat-map, and hold contention because
the seeded show had become occupied by the earlier successful booking paths.
This is an initial local baseline, not a capacity claim. A clean dedicated
show is required for a representative full booking benchmark.

## Isolated-show evidence: 2026-09-02

Show 2 was created with 100 seats so experiments would not consume the demo
show. The 100-request hot-seat test produced exactly one winner, 99 expected
conflicts, and zero unexpected responses in 991.6 ms. The winning hold was
released afterward.

A 15-second run against show 2 used three users and produced 82 requests with
0% measured failures, including successful booking, payment creation, and
simulated confirmation. Aggregate approximate latency was p50 25 ms, p95 160
ms, and p99 210 ms. Four bookings were intentionally left confirmed; twelve
temporary load holds were released during cleanup.

For worker recovery, the run left 8 pending outbox events; together with one
earlier pending event, a restarted Celery worker processed all 9 events into 9
notifications. This demonstrates that booking correctness does not depend on
the worker being available during the request.
