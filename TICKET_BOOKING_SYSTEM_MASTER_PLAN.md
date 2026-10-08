# Scalable Ticket Booking System — Master Learning and Implementation Plan

> **Purpose:** This document is the single source of truth for building a BookMyShow-style ticket-booking system with React, TypeScript, Python Flask, PostgreSQL, Redis, Celery, and WebSockets. It is written for both the learner and coding agents that will help implement it.
>
> **Local-development constraint:** Do **not** use Docker locally. PostgreSQL, Redis, Python, and Node.js must run as native local installations to reduce laptop CPU, RAM, and heat. Docker may be introduced later on the AWS server for deployment only.
>
> **Primary learning goal:** The project exists to learn system design practically. Correctness, explanation, testing, documentation, and measured experiments are more important than generating code quickly.

---

## 1. Instructions for Every Coding Agent

Any coding agent working on this repository must read this entire document before changing code.

### 1.1 Learning-first behaviour

The agent must:

1. Explain the concept being implemented before or alongside the implementation.
2. State why the selected approach is appropriate and mention important alternatives.
3. Break large changes into small, reviewable steps.
4. Add useful comments around concurrency, transactions, idempotency, caching, retries, and non-obvious business rules.
5. Avoid comments that merely repeat obvious code.
6. Create or update documentation whenever behaviour, APIs, database structure, setup, or architecture changes.
7. Include commands the learner can run manually.
8. Explain expected output and common failure cases.
9. Add tests for the success path, validation failures, concurrency, and retry behaviour.
10. Never hide important logic behind unexplained generated abstractions.
11. Prefer readable code over clever code.
12. Pause at the end of each milestone and provide a learning summary.

### 1.2 Required response format for implementation work

For each meaningful task, the agent should report:

1. **Concept:** What system-design or engineering idea is being practised.
2. **Plan:** Files and behaviour that will change.
3. **Implementation:** The code changes.
4. **How to run:** Exact local commands.
5. **How to verify:** Tests and manual checks.
6. **What to observe:** Logs, database state, latency, locks, or failure behaviour.
7. **Documentation:** Documents created or updated.
8. **Learning recap:** What was learned and what trade-offs remain.

### 1.3 Rules for comments and documentation

Comments are especially required when code includes:

- `SELECT ... FOR UPDATE`
- Transaction boundaries
- Idempotency checks
- Lock ordering
- Cache invalidation
- Redis TTL behaviour
- Background retries
- Webhook deduplication
- Outbox processing
- WebSocket reconnection
- Security-sensitive behaviour

Maintain these repository documents as the project grows:

```text
README.md                         Local setup and project overview
docs/architecture.md              Current and target architecture
docs/database.md                  Tables, constraints, indexes and migrations
docs/api.md                       API contracts and error codes
docs/concurrency.md               Seat locking and concurrency experiments
docs/idempotency.md               Idempotency and webhook deduplication
docs/caching.md                   Cache keys, TTLs and invalidation
docs/background-jobs.md           Celery tasks, retries and outbox
docs/testing.md                   Test strategy and commands
docs/load-testing.md              Scenarios and performance results
docs/deployment.md                AWS deployment and recovery steps
docs/decisions/                   Architecture Decision Records (ADRs)
```

Use ADRs for meaningful decisions, for example:

```text
docs/decisions/001-modular-monolith.md
docs/decisions/002-postgresql-source-of-truth.md
docs/decisions/003-pessimistic-locking-for-holds.md
docs/decisions/004-transactional-outbox.md
```

### 1.4 Agent restrictions

The agent must not:

- Introduce local Docker or Docker Compose unless the learner explicitly changes this constraint.
- Start with microservices.
- Use SQLite for transaction or concurrency tests.
- treat Redis as the authoritative owner of a seat.
- Keep a database transaction open while calling an external service.
- Mark a booking successful before authoritative database confirmation.
- Add AWS resources without discussing cost and cleanup.
- Implement a later milestone before the current milestone meets its definition of done.
- Replace explanations with only code.

---

## 2. Project Definition

Build a scalable ticket-booking platform similar to a small BookMyShow. Customers browse events, select a show, view a seat map, temporarily hold seats, simulate payment, confirm bookings, receive notifications, and view booking history. Administrators manage venues, auditoriums, seats, events, shows, and pricing.

The critical invariant is:

> A show seat must never be actively confirmed for two different users, even when requests arrive concurrently, are retried, or are processed by different application instances.

### 2.1 Why this project

This system naturally teaches:

- API design
- Relational data modelling
- Transactions and isolation
- Race conditions and locking
- Idempotency
- Caching and cache invalidation
- TTL and expiration
- Background jobs and message queues
- At-least-once delivery
- Transactional outbox
- WebSockets and real-time synchronization
- Rate limiting
- Authentication and authorization
- Indexing and query analysis
- Load testing
- Observability
- Failure recovery
- Horizontal scaling
- AWS deployment

### 2.2 Terminology

| Entity | Meaning | Example |
|---|---|---|
| Event | The content being presented | A movie or concert |
| Venue | Physical location | PVR Phoenix Mall |
| Auditorium | Bookable room/area in a venue | Screen 3 |
| Seat | Physical seat in an auditorium | A10 |
| Show | Event in an auditorium at a time | Movie at 7:30 PM |
| Show seat | A physical seat’s inventory for one show | A10 for the 7:30 PM show |
| Hold | Temporary reservation | A10 held for five minutes |
| Booking | Purchase record | Confirmed booking BK-123 |
| Payment | One payment attempt for a booking | Successful simulated card payment |

A physical seat belongs to an auditorium. Availability belongs to a **show seat**, because A10 may be booked for 7:30 PM and available for 10:30 PM.

---

## 3. Scope

### 3.1 Customer features

- Register, log in, refresh a session, and log out.
- Select a city.
- Browse, search, filter, and paginate events.
- View event, venue, and show details.
- View a show’s seat layout.
- See available and unavailable seats.
- Select up to ten seats.
- Atomically hold all selected seats for five minutes.
- Release a hold manually.
- Create a pending booking from an active hold.
- Simulate successful, failed, timed-out, and duplicated payments.
- Confirm a booking after successful payment.
- View booking history and details.
- Cancel eligible bookings.
- Receive simulated/email notifications asynchronously.

### 3.2 Administrator features

- Create and update venues.
- Create auditoriums and physical seat layouts.
- Create and update events.
- Schedule shows.
- Configure show-seat prices.
- Cancel shows.
- View bookings and basic sales summaries.

### 3.3 Initially out of scope

- Real card storage or a real payment gateway
- Refund settlement with a provider
- Coupons and loyalty points
- Ratings and reviews
- Recommendations
- Multiple currencies
- Organizer portal
- Elasticsearch/OpenSearch
- Native mobile application
- Multi-region active-active deployment

Payment is simulated intentionally so failure handling can be tested safely.

---

## 4. Non-Functional Requirements

### 4.1 Consistency

| Operation | Requirement |
|---|---|
| Seat hold | Strong consistency |
| Booking confirmation | Strong consistency |
| Booking history | Strong consistency |
| Seat-map display | Nearly real-time; temporary staleness tolerated |
| Event catalogue | Eventual consistency acceptable |
| Notifications | Eventual consistency acceptable |
| Analytics | Eventual consistency acceptable |

### 4.2 Reliability

- A retry must not create a duplicate booking or payment.
- Notification failure must not reverse a booking.
- An expired hold must eventually release its seats.
- Redis failure must not permit double booking.
- Partial confirmation must roll back completely.
- Payment callbacks may arrive more than once and out of order.
- Confirmed booking history must survive application restarts.

### 4.3 Performance targets

| Operation | Target server response time |
|---|---:|
| Browse events | p95 below 300 ms |
| View shows | p95 below 300 ms |
| Load seat layout | p95 below 500 ms |
| Hold seats | p95 below 500 ms |
| Confirm booking | p95 below 1 second, excluding provider wait |
| Search | p95 below 500 ms |

These are learning targets, not initial laptop guarantees.

### 4.4 Security

- Hash passwords with Argon2 or bcrypt.
- Use short-lived access tokens and revocable refresh tokens.
- Enforce role-based authorization.
- Validate all request data.
- Apply rate limits to authentication and hold endpoints.
- Never store card data.
- Remove secrets and personal data from logs.
- Restrict admin APIs to administrators.
- Load secrets from environment variables, never source control.

### 4.5 Observability

Eventually measure:

- Request rate and error rate
- p50, p95, and p99 response latency
- Database query duration
- Lock-wait duration and deadlocks
- Active and expired holds
- Successful and failed bookings
- Payment failures and duplicate callbacks
- Redis cache-hit ratio
- Celery queue length and retry count
- Database connection-pool usage

---

## 5. Scale Assumptions

The laptop implementation will be small, but the logical design targets:

| Metric | Assumption |
|---|---:|
| Registered users | 1,000,000 |
| Daily active users | 100,000 |
| Normal concurrent users | 5,000 |
| Popular-sale concurrent users | 20,000 |
| Events | 10,000 |
| Shows per day | 2,000 |
| Average seats per show | 300 |
| Booking attempts per day | 100,000 |
| Average seats per booking | 2.5 |
| Read/write ratio | Approximately 90:10 |

If users make 3,000,000 requests per day:

```text
Average RPS = 3,000,000 / 86,400 ≈ 35 requests/second
Estimated peak = 35 × 20 ≈ 700 requests/second
```

Popular events can create several thousand requests per second against the same show. Average traffic must never be used as the only capacity input.

---

## 6. Business Rules and State Machines

### 6.1 Seat rules

1. A show seat is `AVAILABLE`, `HELD`, or `BOOKED`.
2. A user can hold multiple seats in one request.
3. All requested seats must be held atomically.
4. If one requested seat is unavailable, the entire hold fails.
5. Holds last five minutes initially.
6. Only the owner of an active hold can use or release it.
7. An expired hold cannot be confirmed.
8. A confirmed seat cannot be actively assigned to another booking.
9. Repeating an operation with the same idempotency key must not duplicate it.
10. A late successful payment cannot take a seat that has been reassigned.
11. Booking prices are snapshots and do not change when future prices change.
12. Cancellation preserves history while allowing the seat to become available again.

### 6.2 Seat lifecycle

```mermaid
stateDiagram-v2
    [*] --> AVAILABLE
    AVAILABLE --> HELD: Create hold
    HELD --> AVAILABLE: Release or expire
    HELD --> BOOKED: Confirm payment
    BOOKED --> AVAILABLE: Eligible cancellation
```

### 6.3 Booking lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING_PAYMENT
    PENDING_PAYMENT --> CONFIRMED: Payment accepted
    PENDING_PAYMENT --> PAYMENT_FAILED: Payment failed
    PENDING_PAYMENT --> EXPIRED: Hold expired
    CONFIRMED --> CANCELLED: Eligible cancellation
```

### 6.4 Payment lifecycle

```mermaid
stateDiagram-v2
    [*] --> INITIATED
    INITIATED --> PROCESSING
    PROCESSING --> SUCCESS
    PROCESSING --> FAILED
    SUCCESS --> REFUND_REQUIRED: Seat no longer confirmable
    SUCCESS --> REFUNDED: Refund completed
```

---

## 7. Architecture

### 7.1 Technology stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite |
| Server state | TanStack Query |
| Backend | Python Flask |
| Validation | Pydantic |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic/Flask-Migrate |
| Database | PostgreSQL |
| Cache and broker | Redis |
| Background jobs | Celery + Celery Beat |
| Real-time updates | Flask-SocketIO |
| Production Python server | Gunicorn |
| Reverse proxy | Nginx |
| Backend testing | Pytest |
| Frontend testing | Vitest + React Testing Library |
| End-to-end testing | Playwright, introduced later |
| Load testing | Locust |

### 7.2 Start with a modular monolith

Do not start with microservices. Use one Flask codebase with clear module boundaries. This provides transaction simplicity and lets us identify real boundaries before splitting anything.

```text
React application
       |
       v
Flask modular monolith
   |              |
   v              v
PostgreSQL      Redis
                  |
                  v
             Celery workers
```

### 7.3 Production target architecture

```mermaid
flowchart TD
    Client[React clients] --> CDN[CDN and static hosting]
    Client --> LB[Load balancer]
    LB --> API[Flask API instances]
    API --> DB[(PostgreSQL primary)]
    API --> Redis[(Redis)]
    API --> WS[WebSocket service]
    Redis --> Worker[Celery workers]
    DB --> Replica[(Read replica)]
    Worker --> Notify[Notification provider]
```

### 7.4 Component responsibilities

**React** renders the UI, requests state, displays the countdown, and handles recoverable conflicts. It never declares a seat held or booked without backend confirmation.

**Flask** performs authentication, validation, catalogue queries, holds, bookings, payments, and administration.

**PostgreSQL** is the authoritative source for inventory, holds, bookings, payments, and audit history.

**Redis** provides caching, TTL hints, rate-limit counters, Celery transport, and Socket.IO coordination. Redis improves performance but never replaces database constraints.

**Celery** handles expiration cleanup, notifications, outbox events, retries, and later analytics work.

**WebSockets** publish seat-status changes. Reconnecting clients must reload the authoritative seat map because WebSocket delivery is not guaranteed.

---

## 8. Repository Structure

```text
ticket-booking-system/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── events/
│   │   ├── venues/
│   │   ├── shows/
│   │   ├── inventory/
│   │   ├── holds/
│   │   ├── bookings/
│   │   ├── payments/
│   │   ├── notifications/
│   │   ├── admin/
│   │   ├── models/
│   │   ├── common/
│   │   ├── extensions.py
│   │   ├── config.py
│   │   └── factory.py
│   ├── migrations/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── concurrency/
│   ├── scripts/
│   ├── celery_worker.py
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── routes/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   └── .env.example
├── load-tests/
├── docs/
│   └── decisions/
├── scripts/
├── .gitignore
├── README.md
└── TICKET_BOOKING_SYSTEM_MASTER_PLAN.md
```

The HTTP route validates HTTP input and calls an application service. Business rules belong in services/domain code, not routes.

---

## 9. Native Local Development Setup — No Docker

The learner commonly works on Windows, so Windows is the primary setup. Linux/macOS equivalents are included briefly.

### 9.1 Required software

- Git
- Python 3.12 or a currently supported Python 3 release
- Node.js 22 LTS or current LTS
- PostgreSQL 16 or newer supported release
- Redis-compatible local server
- VS Code or preferred IDE
- Optional: DBeaver or pgAdmin
- Optional: RedisInsight

Do not install Nginx or Gunicorn for normal Windows development. Vite and Flask development servers are sufficient locally. Gunicorn/Nginx will be used on Linux deployment.

### 9.2 Windows installation

#### Git

Install Git for Windows and verify:

```powershell
git --version
```

#### Python

Install Python from python.org and select **Add Python to PATH**.

```powershell
python --version
python -m pip --version
```

Create a virtual environment later with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

#### Node.js

Install the LTS version and verify:

```powershell
node --version
npm --version
```

#### PostgreSQL

Install PostgreSQL using the official Windows installer. Record the password created for the `postgres` administrator. Include command-line tools and optionally pgAdmin.

Add PostgreSQL’s `bin` directory to `PATH` if `psql` is not recognized, then verify:

```powershell
psql --version
```

Create a development role and database from `psql` or pgAdmin:

```sql
CREATE ROLE ticket_app WITH LOGIN PASSWORD 'replace_with_local_password';
CREATE DATABASE ticket_booking OWNER ticket_app;
CREATE DATABASE ticket_booking_test OWNER ticket_app;
```

Never use the `postgres` superuser from application code.

#### Redis on Windows

The official Redis server is primarily supported on Linux. Choose one native/local approach:

1. **Memurai Developer Edition** on Windows, which is Redis-protocol compatible.
2. **WSL2 + Redis** if WSL2 is already used and does not create unacceptable resource usage.

For the least friction on Windows, use Memurai as a Windows service. Verify with a compatible CLI if installed:

```powershell
redis-cli ping
```

Expected response:

```text
PONG
```

If Redis requires a password:

```powershell
redis-cli -a your_password ping
```

#### Celery on Windows

Celery’s production support is Linux-oriented. For local learning on Windows, run a single-process worker:

```powershell
celery -A celery_worker.celery worker --loglevel=INFO --pool=solo
```

This is appropriate for development but not a production concurrency model. On AWS/Linux, use Celery’s normal prefork worker.

### 9.3 Ubuntu/Debian setup

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip postgresql redis-server nodejs npm
sudo systemctl enable --now postgresql redis-server
```

Create databases using a PostgreSQL administrator account and verify Redis:

```bash
redis-cli ping
```

### 9.4 macOS setup

Using Homebrew:

```bash
brew install git python node postgresql@16 redis
brew services start postgresql@16
brew services start redis
```

### 9.5 Local environment variables

Create `backend/.env` from `backend/.env.example`:

```dotenv
APP_ENV=development
FLASK_DEBUG=true
SECRET_KEY=replace_with_long_random_value
JWT_SECRET_KEY=replace_with_another_long_random_value

DATABASE_URL=postgresql+psycopg://ticket_app:replace_with_local_password@localhost:5432/ticket_booking
TEST_DATABASE_URL=postgresql+psycopg://ticket_app:replace_with_local_password@localhost:5432/ticket_booking_test

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
SOCKETIO_REDIS_URL=redis://localhost:6379/3

ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
HOLD_DURATION_SECONDS=300
MAX_SEATS_PER_HOLD=10
```

Use separate Redis logical databases locally to make responsibilities easier to inspect. In production, separate instances or stronger key-space isolation may be preferable.

Create `frontend/.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:5000/api/v1
VITE_SOCKET_URL=http://localhost:5000
```

Never commit `.env`; commit only `.env.example`.

### 9.6 Local processes

Development uses separate terminals:

| Terminal | Process |
|---|---|
| 1 | PostgreSQL Windows service/native daemon |
| 2 | Redis/Memurai service |
| 3 | Flask API |
| 4 | React Vite server |
| 5 | Celery worker, when introduced |
| 6 | Celery Beat, when introduced |

Typical commands after the repository exists:

```powershell
# Terminal 3: backend
cd backend
.\.venv\Scripts\Activate.ps1
flask --app app.factory:create_app run --debug --port 5000
```

```powershell
# Terminal 4: frontend
cd frontend
npm run dev
```

```powershell
# Terminal 5: worker
cd backend
.\.venv\Scripts\Activate.ps1
celery -A celery_worker.celery worker --loglevel=INFO --pool=solo
```

```powershell
# Terminal 6: scheduler
cd backend
.\.venv\Scripts\Activate.ps1
celery -A celery_worker.celery beat --loglevel=INFO
```

### 9.7 Laptop resource-control guidance

- Do not start Celery, Beat, or WebSockets before their milestones.
- Stop PostgreSQL and Redis services when not working on the project if desired.
- Keep one Flask debug process; avoid unnecessary reloaders if CPU usage is high.
- Keep seed data modest locally.
- Run Grafana/Prometheus only during the observability milestone.
- Run load tests separately, not during normal coding.
- Use database connection pools with low local limits.

---

## 10. Database Model

### 10.1 Main relationships

```mermaid
erDiagram
    USER ||--o{ SEAT_HOLD : creates
    USER ||--o{ BOOKING : makes
    EVENT ||--o{ SHOW : schedules
    VENUE ||--o{ AUDITORIUM : contains
    AUDITORIUM ||--o{ SEAT : contains
    AUDITORIUM ||--o{ SHOW : hosts
    SHOW ||--o{ SHOW_SEAT : offers
    SEAT ||--o{ SHOW_SEAT : becomes
    SEAT_HOLD ||--o{ HOLD_ITEM : contains
    BOOKING ||--o{ BOOKING_ITEM : contains
    BOOKING ||--o{ PAYMENT : has
```

### 10.2 Tables

#### `users`

Important fields:

- `id BIGSERIAL PRIMARY KEY`
- `email VARCHAR(255) UNIQUE NOT NULL`
- `password_hash VARCHAR(255) NOT NULL`
- `full_name VARCHAR(150) NOT NULL`
- `role`: `CUSTOMER` or `ADMIN`
- `status`: `ACTIVE` or `BLOCKED`
- timestamps

#### `venues`

- ID, name, city, address, timezone, timestamps
- Index `city`

#### `auditoriums`

- ID, venue FK, name
- Unique `(venue_id, name)`

#### `seats`

- ID, auditorium FK, row label, seat number, category, active flag
- Unique `(auditorium_id, row_label, seat_number)`

#### `events`

- ID, title, description, category, language, duration, status, timestamps
- Status: `DRAFT`, `ACTIVE`, `INACTIVE`

#### `shows`

- ID, event FK, auditorium FK
- Start/end timestamps
- Booking-open/close timestamps
- Status: `SCHEDULED`, `CANCELLED`, `COMPLETED`
- Indexes `(event_id, starts_at)`, `(auditorium_id, starts_at)`, `(status, starts_at)`
- Later investigate PostgreSQL exclusion constraints to prevent auditorium-time overlap.

#### `show_seats`

This is authoritative show inventory:

```sql
CREATE TABLE show_seats (
    id          BIGSERIAL PRIMARY KEY,
    show_id     BIGINT NOT NULL REFERENCES shows(id),
    seat_id     BIGINT NOT NULL REFERENCES seats(id),
    price       NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    status      VARCHAR(20) NOT NULL
                CHECK (status IN ('AVAILABLE', 'HELD', 'BOOKED')),
    version     INTEGER NOT NULL DEFAULT 1,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (show_id, seat_id)
);

CREATE INDEX idx_show_seats_show_status
    ON show_seats(show_id, status);
```

The `version` column supports an optimistic-locking experiment, even though the primary hold implementation uses pessimistic locking.

#### `seat_holds`

- UUID ID, user FK, show FK
- Status: `ACTIVE`, `CONFIRMED`, `EXPIRED`, `RELEASED`
- `expires_at` and timestamps
- Partial index on `expires_at WHERE status = 'ACTIVE'`

#### `hold_items`

- Hold FK, show-seat FK, price snapshot
- Unique `(hold_id, show_seat_id)`

#### `bookings`

- UUID ID and unique booking reference
- User/show/hold FKs
- Status: `PENDING_PAYMENT`, `CONFIRMED`, `PAYMENT_FAILED`, `CANCELLED`, `EXPIRED`
- Amount, currency, idempotency key, timestamps
- Unique `(user_id, idempotency_key)`
- Unique `hold_id`

#### `booking_items`

Preserve historical items while allowing cancelled seats to be sold again:

```sql
CREATE TABLE booking_items (
    id              BIGSERIAL PRIMARY KEY,
    booking_id      UUID NOT NULL REFERENCES bookings(id),
    show_seat_id    BIGINT NOT NULL REFERENCES show_seats(id),
    seat_label      VARCHAR(30) NOT NULL,
    unit_price      NUMERIC(10, 2) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (booking_id, show_seat_id)
);

CREATE UNIQUE INDEX uq_active_booking_show_seat
    ON booking_items(show_seat_id)
    WHERE is_active = TRUE;
```

On eligible cancellation, set the historical item’s `is_active` to false and the locked `show_seat` to `AVAILABLE` within the same transaction.

#### `payments`

- UUID ID and booking FK
- Provider and provider payment ID
- Unique idempotency key
- Amount and currency
- Status: `INITIATED`, `PROCESSING`, `SUCCESS`, `FAILED`, `REFUND_REQUIRED`, `REFUNDED`
- Failure reason and timestamps
- Unique `(provider, provider_payment_id)` where applicable

#### `webhook_events`

- Unique provider event ID
- Provider, event type, payload, processing status, timestamps
- Used to deduplicate provider callbacks.

#### `outbox_events`

- UUID ID, event type, aggregate type/ID, JSONB payload
- Status: `PENDING`, `PROCESSING`, `PROCESSED`, `FAILED`
- Retry count, available time, processed time, created time
- Written in the same transaction as the booking change.

#### `booking_audit_logs`

- Booking FK, action, previous/new status, JSONB metadata, timestamp
- Used for incident investigation and learning.

### 10.3 Required database principles

- Application checks improve error messages; database constraints provide final enforcement.
- Money uses `NUMERIC`, never floating point.
- Times are stored as UTC `TIMESTAMPTZ`; venue timezone controls display.
- Use migrations for every schema change.
- Never manually alter shared schemas without a migration.
- Use PostgreSQL in integration and concurrency tests.

---

## 11. API Contract

All endpoints begin with `/api/v1`.

### 11.1 Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Register |
| POST | `/auth/login` | Login |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Revoke refresh token |
| GET | `/users/me` | Current user |
| GET | `/events` | Paginated/filterable catalogue |
| GET | `/events/{id}` | Event detail |
| GET | `/events/{id}/shows` | Event shows |
| GET | `/shows/{id}` | Show detail |
| GET | `/shows/{id}/seats` | Seat map |
| POST | `/shows/{id}/holds` | Atomically hold seats |
| GET | `/holds/{id}` | Hold detail and expiry |
| DELETE | `/holds/{id}` | Release own hold |
| POST | `/bookings` | Create booking from hold |
| GET | `/bookings` | User booking history |
| GET | `/bookings/{id}` | Booking detail |
| POST | `/bookings/{id}/cancel` | Eligible cancellation |
| POST | `/payments` | Start simulated payment |
| POST | `/payments/{id}/simulate` | Simulate outcome |
| POST | `/webhooks/payments` | Payment callback |

Admin CRUD endpoints live below `/api/v1/admin`.

### 11.2 Pagination

Initial catalogue APIs may use page/page-size offset pagination. Later, implement or document cursor pagination and compare behaviour for growing/changeable datasets.

### 11.3 Standard error response

```json
{
  "error": {
    "code": "SEATS_UNAVAILABLE",
    "message": "One or more selected seats are no longer available.",
    "details": {
      "unavailable_show_seat_ids": [9002]
    },
    "request_id": "req-55c774"
  }
}
```

| HTTP status | Use |
|---:|---|
| 400 | Malformed or invalid request |
| 401 | Missing/invalid authentication |
| 403 | Authenticated but forbidden |
| 404 | Missing resource |
| 409 | State conflict or idempotency conflict |
| 422 | Valid data but prohibited business operation |
| 429 | Rate limit exceeded |
| 500 | Unexpected internal error |
| 503 | Temporary dependency failure |

### 11.4 Hold request example

```http
POST /api/v1/shows/501/holds
Authorization: Bearer <token>
Idempotency-Key: hold-a891c
Content-Type: application/json
```

```json
{
  "show_seat_ids": [9001, 9002, 9003]
}
```

Successful response returns the hold ID, selected seat snapshots, total, status, and UTC expiration timestamp.

### 11.5 Idempotency

Require `Idempotency-Key` for mutating operations where retries can duplicate business effects:

- Create hold
- Create booking
- Start payment
- Cancel booking
- Process payment callback, using provider event ID

Store a combination such as:

```text
user/consumer identity + operation + idempotency key + request hash + stored response
```

Rules:

- Same key and same request returns the original result.
- Same key and different request returns `409 IDEMPOTENCY_KEY_REUSED`.
- Concurrent requests with the same key result in one operation.
- Retention duration must be documented.

---

## 12. Correct Concurrent Seat-Hold Algorithm

### 12.1 Authoritative workflow

1. Validate authentication and input.
2. Deduplicate and sort requested show-seat IDs.
3. Begin a PostgreSQL transaction.
4. Validate the show and booking window.
5. Lock requested `show_seats` in ascending ID order with `FOR UPDATE`.
6. Confirm every requested ID belongs to the show.
7. Lazily release expired holds encountered by the locked seats.
8. If any seat remains unavailable, roll back the whole operation.
9. Create the hold and hold items.
10. Change all seats to `HELD` and increment versions.
11. Commit.
12. Best-effort write a Redis TTL key.
13. Invalidate cached seat-map data and publish a real-time event.

Conceptual query:

```sql
SELECT *
FROM show_seats
WHERE show_id = :show_id
  AND id = ANY(:sorted_seat_ids)
ORDER BY id
FOR UPDATE;
```

### 12.2 Why sorting matters

If request A locks A1 then A2 while request B locks A2 then A1, they can deadlock. Consistent ascending lock order makes both request rows in the same order. PostgreSQL still detects unexpected deadlocks, and the application should retry only carefully selected transient transaction failures.

### 12.3 Why a simple application check fails

This is unsafe:

```python
if seat.status == "AVAILABLE":
    seat.status = "HELD"
    session.commit()
```

Two application processes can both read `AVAILABLE` before either commits. Database row locks plus constraints are required.

### 12.4 Redis role

Redis stores a TTL hint such as:

```text
hold:{hold_id} -> user_id, TTL 300 seconds
```

Redis does not own the seat. A Redis restart, missing key, or delayed expiration event must not violate correctness.

### 12.5 Expiration

Use both:

1. **Lazy expiration:** A seat/hold request locks and releases an expired hold it encounters.
2. **Scheduled cleanup:** Celery Beat schedules batch cleanup.

Cleanup query pattern:

```sql
SELECT id
FROM seat_holds
WHERE status = 'ACTIVE'
  AND expires_at <= NOW()
ORDER BY expires_at
FOR UPDATE SKIP LOCKED
LIMIT 100;
```

`SKIP LOCKED` permits several workers to claim different batches without waiting on the same rows.

### 12.6 Required concurrency test

Create 100 concurrent attempts for one show seat using separate database sessions/connections. Exactly one hold must succeed, 99 must receive an expected conflict, and the database must contain exactly one active hold item for that seat.

---

## 13. Booking and Payment Workflow

### 13.1 Never call an external provider inside a database transaction

Correct separation:

1. Create pending booking and commit.
2. Start provider/simulated payment outside that transaction.
3. Receive result or webhook.
4. Start a new transaction.
5. Deduplicate and lock webhook/payment/booking/hold/seats.
6. Confirm all state atomically.

### 13.2 Confirmation transaction

- Deduplicate provider event.
- Lock payment.
- Lock booking.
- Lock hold.
- Lock held seats in consistent order.
- Verify ownership and current states.
- If hold expired, mark `REFUND_REQUIRED`; never steal reassigned seats.
- Set payment `SUCCESS`.
- Set booking `CONFIRMED`.
- Set hold `CONFIRMED`.
- Set seats `BOOKED`.
- Create active booking items.
- Insert booking audit record.
- Insert `BOOKING_CONFIRMED` outbox event.
- Commit everything together.

### 13.3 Transactional outbox

Without an outbox, the booking may commit and the process may crash before enqueueing a notification. Insert the booking change and outbox row in one PostgreSQL transaction. A worker later claims and processes outbox rows.

Design for at-least-once processing: the same outbox event may be attempted repeatedly, so consumers must be idempotent.

---

## 14. Caching and Real-Time Updates

### 14.1 Cache-aside strategy

1. Read cache.
2. On hit, return cached data.
3. On miss, query PostgreSQL.
4. Store response with TTL.
5. Return it.

| Data | Cache? | Initial TTL |
|---|---|---:|
| Event details | Yes | 5–15 minutes |
| Venue details | Yes | 30 minutes |
| Show listings | Yes | 1–5 minutes |
| Seat map | Carefully | A few seconds |
| Booking detail | No initially | — |
| Analytics summary | Yes later | 1–10 minutes |

Seat-map cache is display-only. Hold creation always revalidates PostgreSQL.

### 14.2 Cache invalidation

- Admin event update: commit database, then remove relevant event/list keys.
- Seat state change: commit database, invalidate show seat-map cache, publish WebSocket event.
- If invalidation fails, short TTL provides bounded staleness.

Later test cache stampede protection using a per-key lock or stale-while-revalidate approach.

### 14.3 WebSocket event

```json
{
  "type": "SEAT_STATUS_CHANGED",
  "show_id": 501,
  "seat_ids": [9001, 9002],
  "status": "HELD",
  "seat_map_version": 38
}
```

Clients join a `show:501` room. On reconnect or version gap, reload `/shows/501/seats` rather than assuming no event was missed.

---

## 15. Milestone Plan

Assume 1–2 hours per day, five days per week. Eight weeks is an estimate, not a deadline.

### Milestone 0 — Foundation (2–3 days)

Build:

- Git repository and folder structure
- Native Python virtual environment
- Flask application factory
- PostgreSQL and Redis configuration
- SQLAlchemy and Alembic
- Pydantic validation foundation
- React TypeScript application
- `/health/live` and `/health/ready`
- Pytest and frontend test setup
- README and first ADRs

Definition of done:

- API, database, Redis, and frontend run natively.
- Readiness reports dependency state.
- Automated foundation tests pass.
- Another developer can follow README setup from zero.

### Milestone 1 — Authentication (3–4 days)

- Registration/login/logout/refresh
- Password hashing
- Access and refresh-token lifecycle
- Role-based authorization
- Protected React routes
- Auth tests and documentation

### Milestone 2 — Catalogue (4–5 days)

- Venues, auditoriums, seats, events, shows
- Admin CRUD
- Pagination and filtering
- Seed script: 5 venues, 10 auditoriums, ~1,500 seats, 20 events, 50–100 shows
- Event list/detail/show UI
- Query/index experiments

### Milestone 3 — Seat inventory (3–4 days)

- Create `show_seats` from active auditorium seats
- Show-specific pricing
- Seat-layout API
- Interactive React seat map
- Availability/category/selection display

### Milestone 4 — Concurrent holds (5–7 days)

- Holds, hold items, five-minute expiry
- Pessimistic row locking
- Atomic group hold
- Lock ordering
- Redis TTL hint
- Idempotency
- Lazy and scheduled cleanup
- Conflict UI and countdown
- Concurrency experiments and documentation

Definition of done: 100 competing attempts produce exactly one active hold.

### Milestone 5 — Booking and simulated payment (5–6 days)

- Pending booking and booking items
- Payment attempts
- Success/failure/timeout/duplicate callbacks
- Webhook deduplication
- Atomic confirmation
- Late-success/refund-required handling
- Audit history
- Booking history UI

Definition of done: repeated requests and callbacks never create duplicate business effects.

### Milestone 6 — Background processing (3–4 days)

- Celery worker and Beat
- Expiration batches
- Transactional outbox
- Simulated notification consumer
- Retry with exponential backoff and jitter
- Failed-event handling

Definition of done: booking succeeds while worker is down; notification processes after restart.

### Milestone 7 — Cache and real time (4–5 days)

- Cache-aside for catalogue
- Invalidation and TTLs
- Cache-hit measurement
- Socket.IO show rooms
- Seat events, reconnection, and version checks

### Milestone 8 — Security and rate limits (2–3 days)

- Login and hold rate limits
- Seat-per-hold limit
- CORS and security headers
- Request size and schema limits
- Secret and log review
- Admin authorization tests

### Milestone 9 — Load and failure testing (4–6 days)

- Locust browse/seat/hold/booking scenarios
- Hot-seat contention
- Duplicate callbacks
- p50/p95/p99 reports
- Compare indexes, cache, and worker counts
- Stop Redis, Celery, and Flask during controlled experiments
- Document bottleneck and improvement evidence

### Milestone 10 — AWS deployment (3–5 days)

- Check current AWS eligibility and credits before provisioning
- Create budget and usage alerts
- Launch one eligible EC2 instance initially
- Docker is allowed on the Linux EC2 server
- Nginx, HTTPS, Flask/Gunicorn, React, PostgreSQL, Redis, and Celery
- Persistent storage and backups
- Restart/recovery tests
- Teardown instructions

Avoid managed NAT Gateway, load balancer, RDS, and ElastiCache in the first learning deployment because they can consume credits quickly. Later, design the managed production version separately.

---

## 16. Testing Strategy

### 16.1 Test levels

| Level | Purpose |
|---|---|
| Unit | Business rules without external infrastructure |
| Integration | Flask + real PostgreSQL + Redis |
| Concurrency | Separate connections competing for inventory |
| Contract | API request/response compatibility |
| End-to-end | Browser through booking outcome |
| Load | Throughput, latency, contention, saturation |
| Failure | Dependency outage and restart recovery |

### 16.2 Important test cases

- Duplicate registration requests
- Expired and revoked tokens
- Invalid admin access
- Pagination boundary cases
- Overlapping shows in one auditorium
- Invalid show-seat IDs mixed with valid IDs
- Two users hold the same seat
- Overlapping multi-seat requests
- Same idempotency key concurrently
- Hold expires during payment
- Redis unavailable during hold creation
- Duplicate and out-of-order webhooks
- Process stops after DB commit but before response
- Worker is unavailable during booking
- Cancelled seat becomes available while history remains

### 16.3 Load-test experiments

For each experiment, record configuration, dataset, command, timestamps, result, bottleneck, and conclusion.

1. Without versus with catalogue indexes.
2. Without versus with Redis cache.
3. One versus several Gunicorn workers on Linux.
4. Different database pool sizes.
5. Uniform seat demand versus one hot show/seat.
6. One versus several Celery workers.
7. Cache restart during read traffic.
8. API restart during idempotent booking retries.

---

## 17. Git and Delivery Workflow

Use milestone branches:

```text
feature/project-foundation
feature/authentication
feature/event-catalogue
feature/seat-inventory
feature/seat-holds
feature/booking-payment
feature/background-workers
feature/realtime-updates
feature/load-testing
feature/aws-deployment
```

Each change/PR should include:

- Problem and concept
- Solution and alternatives
- Files changed
- Migration impact
- API examples
- Tests added and commands run
- Documentation updated
- Known limitations
- UI screenshots when relevant

Commit messages should describe the business change, for example:

```text
feat(holds): lock show seats before creating atomic hold
test(holds): verify one winner under concurrent requests
docs(concurrency): explain ordered pessimistic locking
```

---

## 18. AWS Learning Deployment and Evolution

### 18.1 Initial deployment

Use one EC2 server to keep architecture visible and cost controlled:

```text
Internet
  -> Nginx/HTTPS
     -> React static build
     -> Flask/Gunicorn
     -> Socket.IO
        -> local PostgreSQL on EC2
        -> local Redis on EC2
        -> Celery worker on EC2
```

This is not highly available and has a single failure domain. That limitation must be documented rather than hidden.

### 18.2 Evolution exercises

| Evolution | Concept |
|---|---|
| Multiple Gunicorn workers | Process concurrency |
| Multiple API instances | Horizontal scaling |
| External PostgreSQL/RDS design | Independent persistence |
| External Redis/ElastiCache design | Shared cache and coordination |
| Separate Celery workers | Workload isolation |
| Load balancer | Distribution and health checks |
| Read replica | Read scaling and replica lag |
| CDN/static hosting | Edge delivery |
| Service extraction only when justified | Microservice trade-offs |

Do not claim an evolution improves the system until a test or explicit production requirement justifies it.

---

## 19. Learning Checkpoints

At the end of each milestone, the learner should be able to answer these without reading code.

### Foundation

- Why use an application factory?
- What is a migration, and why not edit production tables manually?
- What is liveness versus readiness?
- Why use different development and test databases?

### Catalogue and database

- Why is seat availability not stored on the physical `seats` table?
- What does each index optimize, and what does it cost?
- When does offset pagination become problematic?
- Why store timestamps in UTC?

### Concurrency

- Demonstrate the double-booking race.
- Explain `FOR UPDATE`.
- Why lock seats in sorted order?
- Why is Redis alone insufficient?
- What does transaction isolation guarantee here?
- Compare pessimistic and optimistic locking.

### Idempotency and payments

- What failure does idempotency solve that locking does not?
- Why can a webhook arrive more than once?
- Why avoid external calls inside transactions?
- What happens when payment succeeds after expiration?

### Queues

- What does at-least-once delivery mean?
- Why must consumers be idempotent?
- What problem does the outbox solve?
- When should a task retry, fail permanently, or move to manual review?

### Caching and WebSockets

- What is cache-aside?
- Why is invalidation difficult?
- What happens during a cache stampede?
- Why must a reconnected WebSocket client reload state?

### Performance and scaling

- Difference between latency and throughput?
- Why report p95/p99 rather than only average?
- What is the first measured bottleneck?
- What is a hot row or hot key?
- When would splitting a service help or hurt?

---

## 20. Definition of Project Completion

The project is complete when:

- A new developer can run it locally without Docker using documented steps.
- A customer can register, browse, hold seats, pay, and view a confirmed booking.
- Administrators can configure inventory.
- 100 concurrent requests for one seat produce exactly one winner.
- Duplicate HTTP requests and webhooks do not duplicate effects.
- Expired holds are reclaimed correctly.
- Redis or notification-worker failure does not allow double booking.
- Booking and outbox changes are atomic.
- Two browsers receive real-time seat changes and recover after reconnecting.
- Load-test results and bottlenecks are documented.
- The application is deployed on AWS with cost alerts and recovery instructions.
- Architecture, database, API, concurrency, caching, background jobs, tests, and deployment documents reflect the actual code.
- The learner can explain the system and its trade-offs in a system-design interview.

---

## 21. First Task for a Coding Agent

Start only with **Milestone 0 — Foundation**.

The agent must:

1. Inspect the host operating system and installed versions.
2. Do not install or invoke Docker locally.
3. List missing prerequisites and provide native installation guidance.
4. Scaffold the repository structure.
5. Create the Flask application factory and configuration classes.
6. Configure native PostgreSQL and Redis connections through environment variables.
7. Add liveness and readiness endpoints.
8. Configure SQLAlchemy, Alembic, Pydantic, and Pytest.
9. Create the React TypeScript Vite frontend.
10. Add a frontend health/status screen that calls readiness.
11. Add `.env.example` files and protect real `.env` files.
12. Write `README.md`, architecture overview, and initial ADRs.
13. Add and run foundation tests.
14. Stop and provide the milestone learning recap before starting authentication.

The agent should ask for clarification only when the missing choice materially changes the design. Otherwise it should use the defaults in this document, record the decision, and proceed one reviewable step at a time.

