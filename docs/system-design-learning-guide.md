# System design learning guide

This project is a practical way to learn how a production-style booking system
is designed. Each choice answers three questions: what is the concept, why is
it needed, and how does this code implement it?

## 1. Requirements

Functional requirements describe what users can do: browse events, view shows,
select seats, hold seats temporarily, pay, view bookings, and cancel. Non-
functional requirements describe how well the system must behave: no double
booking, predictable failure behaviour, acceptable latency, secure accounts,
and recovery after dependency outages.

This distinction matters because a feature can work in a demo while violating
an important system property. A seat screen can look correct but still allow
two users to purchase the same seat under concurrent requests. See
[architecture](architecture.md) and [API](api.md).

## 2. Request path and architecture

The browser calls Flask over HTTP. Flask validates the request, authenticates
the user, and asks PostgreSQL to read or change authoritative state. Redis may
speed up reads or provide coordination, and Celery processes work after the
request. The frontend receives a response and may also receive a realtime
invalidation event.

```text
Browser -> Flask API -> PostgreSQL (truth)
             |             |
             +-> Redis    +-> committed outbox -> Celery -> notification
             +-> Socket.IO -> browsers in a show room
```

The application is currently a modular monolith: one deployable Flask
application with clear modules for auth, catalogue, holds, bookings, and jobs.
This keeps the learning and deployment surface small while preserving useful
boundaries. See [architecture](architecture.md).

## 3. PostgreSQL as source of truth

The source of truth is the system allowed to decide correctness. Seat
ownership, holds, bookings, payments, and webhook records live in PostgreSQL.
Redis is fast but can restart, lose keys, or return stale data, so it cannot
decide who owns a seat.

A relational database is useful here because transactions, foreign keys,
unique constraints, indexes, and row locks directly express booking rules.
Alembic migrations make schema changes repeatable. See [database](database.md)
and ADR 002.

## 4. Transactions and concurrency

A transaction groups changes into one all-or-nothing unit. Concurrency means
multiple requests can run at the same time. The hot-seat problem is the race
where two requests both observe an available seat.

Hold creation locks selected `show_seats` rows with `FOR UPDATE`, in ascending
ID order, checks every seat, and changes all seats together. The lock makes a
competing transaction wait; the second transaction then sees committed state
and receives `409 SEATS_UNAVAILABLE`. Consistent lock order also reduces
deadlocks. See [concurrency](concurrency.md).

## 5. Idempotency and retries

Networks can fail after a server commits but before the client receives the
response. Clients retry, so write endpoints accept an `Idempotency-Key`.
PostgreSQL stores the key in the request's ownership scope and returns the
original result for a repeat. This prevents duplicate holds, bookings, and
payments.

Idempotency solves duplicate requests; database locks solve simultaneous
ownership races. They are different protections. Payment webhooks use a
unique provider event ID because providers may deliver callbacks repeatedly.
See [idempotency](idempotency.md).

## 6. Payment and atomic confirmation

The simulated payment is intentionally asynchronous. A booking starts as
`PENDING_PAYMENT`; only a payment success event can confirm it. Confirmation
locks the payment, booking, hold, and seats, verifies that the hold is still
active, then changes payment, booking, hold, and seat status in one transaction.
A late success becomes `REFUND_REQUIRED` instead of booking a released seat.

External payment providers must not be called while this database transaction
is open. Network latency would hold database locks and make failure handling
unpredictable.

## 7. Cache and realtime updates

Cache-aside means checking Redis first, using a valid cached response, and
otherwise reading PostgreSQL then populating Redis. It reduces repeated
catalogue reads, but every cache value is disposable. Seat-map writes
invalidate the cache after commit.

WebSockets are for fast display updates, not correctness. A
`SEAT_STATUS_CHANGED` event tells browsers to reload the authoritative seat
map. If a client misses an event, it converges by fetching the complete map
after reconnect. See [caching](caching.md) and [realtime](realtime.md).

## 8. Background jobs and the outbox pattern

Slow or retryable work should not delay the booking transaction. The outbox
pattern writes an event in the same transaction as the booking, then a Celery
worker reads committed events and creates notifications. If Celery is down,
the booking remains correct and the event waits. Unique event identity makes
worker retries safe. See [background jobs](background-jobs.md).

## 9. Security and abuse control

Passwords are stored as Argon2 hashes, not plaintext. Short-lived access JWTs
authorize API requests; refresh tokens are stored by hash and rotated. Pydantic
validates request shapes, CORS limits browser origins, security headers reduce
browser risks, request-size limits reduce abuse, and Redis fixed-window limits
protect registration, login, and holds.

The limiter fails open during a Redis outage to preserve availability. This is
a deliberate trade-off requiring monitoring in production. See
[security](security.md).

## 10. Testing and failure thinking

Unit tests check rules in isolation. Integration tests exercise database and
Redis boundaries. Concurrency tests use separate requests or sessions. Load
tests measure throughput and p50/p95/p99 latency. Failure tests stop a
dependency and verify invariants still hold.

The central invariant is: **one seat cannot have two active owners**. Other
invariants include duplicate callbacks not duplicating confirmation,
notification failure not reversing a booking, and PostgreSQL outage failing
authoritative writes rather than pretending they succeeded. See [testing](testing.md),
[failure testing](failure-testing.md), and [load testing](load-testing.md).

## 11. Scaling vocabulary

- Throughput: completed requests or bookings per second.
- Latency: time for one request; p50 is typical, p95/p99 expose slow tails.
- Horizontal scaling: run more API workers. Shared Redis coordination and
  PostgreSQL locking keep workers consistent.
- Vertical scaling: give one machine more CPU, memory, or database capacity.
- Bottleneck: the resource limiting throughput, such as database locks,
  connection pool capacity, CPU, or a slow dependency.
- Availability versus consistency: stale seat display can improve availability,
  but final seat ownership must remain strongly consistent in PostgreSQL.

Numbers without the scenario, workload, and failure conditions are not useful
performance evidence.
