# Complete learning walkthrough

This document explains what was built, why each part exists, and how a request
moves through the system. Read it before the AWS deployment milestone.

## 1. What we are building

This is a simplified BookMyShow-style ticket system. A customer can browse an
event, choose a show, select seats, temporarily hold them, pay with a
simulated provider, and view or cancel a booking. An administrator manages
catalogue data.

The hardest requirement is not displaying a seat. It is guaranteeing that two
customers cannot successfully own the same seat at the same time.

## 2. Repository map

```text
backend/app/
  auth/       registration, login, JWTs, refresh tokens, admin authorization
  catalogue/ events, venues, auditoriums, shows, show-seat APIs
  holds/      temporary reservations, row locks, idempotency
  bookings/   bookings, payments, webhooks, confirmation, cancellation
  tasks/      expired-hold cleanup and outbox notification worker
  common/     cache and Prometheus metrics helpers
  models/     SQLAlchemy database tables
  factory.py  application assembly and middleware
  run.py      Socket.IO-compatible development server
frontend/src/
  main.tsx    React screens and user flow
  api.ts      HTTP client and authentication header
  bookingState.ts  testable frontend booking rules
migrations/   versioned database schema changes
scripts/      seed data, connectivity, and concurrency experiments
load-tests/   Locust workload
docs/         explanations, decisions, tests, and measured evidence
```

## 3. How to start the system

PostgreSQL and Redis run as local Docker dependencies because Redis was not
available as a native Windows service. The application, frontend, and Celery
worker run natively.

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker start ticket-booking-postgres
& $docker start ticket-booking-redis

cd backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe scripts\seed_catalogue.py
```

Run these in separate terminals:

```powershell
# API
cd backend
.\.venv\Scripts\python.exe run.py

# Frontend
cd frontend
npm run dev -- --host=127.0.0.1

# Background worker
cd backend
.\.venv\Scripts\celery.exe -A celery_worker.celery worker --loglevel=INFO --pool=solo
```

Check `http://127.0.0.1:5000/health/live`,
`http://127.0.0.1:5000/health/ready`, and open
`http://127.0.0.1:5173/`.

## 4. PostgreSQL: what is stored and why

PostgreSQL is the authoritative database. A transaction is a group of changes
that commits together or rolls back together.

- `users`: account identity, password hash, role, and status.
- `refresh_tokens`: hashed refresh tokens that can be revoked.
- `venues`, `auditoriums`, `seats`: reusable physical catalogue structure.
- `events`, `shows`: what is playing and when.
- `show_seats`: one inventory row per physical seat per show. This row owns
  `AVAILABLE`, `HELD`, or `BOOKED` status, price, and version.
- `seat_holds`, `hold_items`: temporary ownership and its selected seats.
- `bookings`, `booking_items`: pending or confirmed customer purchase.
- `payments`: simulated payment attempts and provider identifiers.
- `webhook_events`: provider callback deduplication records.
- `outbox_events`: committed work waiting for Celery.
- `booking_audit_logs`, `notifications`: history and simulated delivery.

Alembic migrations `0001` through `0007` create this structure. Migration
`0007` adds the `(show_id, seat_id)` lookup index. Database constraints and
transactions are the final protection; application checks improve errors.

## 5. Redis: exactly what we write

Redis is an acceleration and coordination system, not the seat authority.

### Catalogue cache

The API checks keys such as `catalogue:events:<query>` and
`catalogue:show:<id>:seats`. On a miss it reads PostgreSQL and writes JSON with
a TTL. A hit avoids a database read. A write invalidates the relevant key
after the database commit.

### Hold TTL hint

After a hold commits in PostgreSQL, the API writes `hold:<hold_id>` with a
five-minute expiration. This is only a cleanup/display hint. A missing Redis
key never makes a seat available or booked.

### Rate limits

Redis counters track registration, login, and hold attempts in fixed windows.
They protect the API from bursts. If Redis is down, the limiter fails open so
a valid PostgreSQL booking is not rejected as though it were invalid.

### Celery and Socket.IO

Redis database 1 transports Celery tasks, database 2 stores task results, and
database 3 coordinates Socket.IO messages between workers. These are
recoverable coordination data, not business truth.

Redis clients have bounded timeouts. Cache failures are logged and fall back to
PostgreSQL; readiness still reports Redis as unavailable.

## 6. A hold request from browser to database

1. React sends `POST /shows/{id}/holds` with seat IDs and an
   `Idempotency-Key`.
2. Flask validates the JWT and request schema.
3. The API locks requested `show_seats` rows with `FOR UPDATE` in ascending
   ID order.
4. It checks every seat is available.
5. It creates a hold and hold items, changes all seats to `HELD`, and commits.
6. Only after commit does it write the Redis TTL hint, invalidate the seat
   cache, and publish a Socket.IO event.
7. The browser reloads the complete seat map after the event.

If two requests race, one transaction gets the lock first. The other waits,
then sees `HELD` and receives `409 SEATS_UNAVAILABLE`. This is why locking and
consistent lock order matter.

## 7. Booking and payment

Creating a booking copies held seat labels and prices into booking items, then
commits `PENDING_PAYMENT`. Payment creation is separate and idempotent. The
simulated callback locks payment, booking, hold, and seats, checks the hold is
still active, and atomically changes them to success, confirmed, confirmed,
and booked.

A late payment success cannot book a released seat. It becomes
`REFUND_REQUIRED`. Duplicate provider callbacks are identified by unique event
IDs.

## 8. Celery and the outbox

The booking transaction writes an outbox event at the same time as
confirmation. The API does not wait for notification delivery. Celery later
locks pending events with `SKIP LOCKED`, creates an idempotent notification,
and marks the event processed. If the worker is down, the booking remains
correct and the event waits.

## 9. Frontend state

React stores server data (`events`, `shows`, `seats`, `bookings`) separately from
temporary user intent (`selected`) and temporary server state (`hold`). The
countdown is derived from `hold.expires_at`; when it reaches zero, the UI
clears the selection and reloads the server seat map. Client disabling is only
usability—the backend always revalidates.

## 10. Security

Argon2 hashes passwords. Short-lived JWT access tokens protect APIs. Refresh
tokens are hashed and rotated. Pydantic validates request shape.
`require_admin` checks the database role after authentication. CORS,
request-size limits, security headers, rate limits, and bounded dependency
timeouts reduce abuse and failure impact.

## 11. How we test correctness

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm test
npm run build
```

Tests cover authentication, authorization, validation, holds, idempotency,
payment callbacks, cancellation, outbox jobs, cache failure, realtime rooms,
metrics, and database failure mapping.

The live contention experiment is:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_load_test_show.py
$env:LOAD_SHOW_ID = "2"
$env:LOAD_SHOW_SEAT_ID = "11"
.\.venv\Scripts\python.exe scripts\concurrency_hold_test.py
```

The invariant is exactly one winner and 99 conflicts. Locust measures
throughput and p50/p95/p99 latency. Redis, PostgreSQL, and Celery are stopped
one at a time to test recovery.

## 12. What to observe

- API responses and status codes: business conflict or infrastructure failure?
- PostgreSQL seat status before and after a race.
- Redis cache hit/miss counters at `/metrics`.
- Outbox status before and after worker restart.
- Locust latency percentiles and error classification.
- Logs showing timeout, cache, or dependency behavior.

## 13. Learning sequence before AWS

1. Run the local flow and inspect API responses.
2. Read the hold route and corresponding tests together.
3. Run the 100-request contention experiment.
4. Inspect Redis cache keys and PostgreSQL rows.
5. Stop Redis and observe graceful degradation.
6. Stop PostgreSQL and observe `503 DEPENDENCY_UNAVAILABLE`.
7. Stop Celery, confirm a booking, restart it, and inspect outbox recovery.
8. Run Locust and compare cache cold/warm latency.
9. Only then study AWS, where these responsibilities map to processes,
   networking, persistent storage, and recovery procedures.
