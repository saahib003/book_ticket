# Ticket Booking System

Learning-focused BookMyShow-style ticket booking system. The master plan in
`TICKET_BOOKING_SYSTEM_MASTER_PLAN.md` is the source of truth.

## Current milestone

Milestone 0 — Foundation. Docker Desktop is currently used only for local
PostgreSQL and Redis dependencies because the native Redis setup is unavailable
on this Windows machine. The application itself runs natively.

## Local dependencies

Start the project-managed PostgreSQL and Redis containers:

```powershell
docker compose -f docker-compose.local.yml up -d
```

PostgreSQL is exposed on `localhost:5433` to avoid the existing native service
on port `5432`. Redis is exposed on `localhost:6379`. Stop them when finished:

```powershell
docker compose -f docker-compose.local.yml down
```

The database data is retained in named Docker volumes. Remove those volumes
only when intentionally resetting local data.

The beginner-friendly system-design explanation is in
`docs/system-design-learning-guide.md`. The complete fresher walkthrough is
in `docs/complete-learning-walkthrough.md`. Detailed library explanations are
in `docs/libraries.md`. Frontend flow is in `docs/frontend.md`; admin
authorization is in `docs/admin.md`; observability is in
`docs/observability.md`; performance evidence is in
`docs/performance-report.md`. Database, API, concurrency, idempotency,
background-job, security, failure-testing, and deployment details are in the
other files under `docs/`.

Razorpay Test Mode setup and payment verification are documented in
`docs/razorpay.md`.

For copy-paste Windows PowerShell commands to run and verify the whole local
system, use `RUN_AND_CHECK_COMMANDS.md`.

Apply migrations and seed local catalogue data:

```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe scripts/seed_catalogue.py
```

## Run the complete local flow

Use separate terminals:

```powershell
# Terminal 1 — dependencies
docker ps

# Terminal 2 — API
cd backend
.\.venv\Scripts\python.exe run.py

# Terminal 3 — frontend
cd frontend
npm run dev -- --host=127.0.0.1

# Terminal 4 — Celery worker, when background processing is needed
cd backend
.\.venv\Scripts\celery.exe -A celery_worker.celery worker --loglevel=INFO --pool=solo
```

Open `http://127.0.0.1:5173/`. The API readiness response should show
PostgreSQL and Redis as `ok`. Register a customer, select seats, hold them,
and click Pay. The simulated payment should confirm the booking.

Common failures:

- `503 not_ready`: check that both dependency containers are running and that
  `backend/.env` uses PostgreSQL port `5433` and Redis port `6379`.
- `ECONNREFUSED`: the Flask or Vite process is not running on its documented
  port.
- `EMAIL_ALREADY_REGISTERED`: use a new email or inspect the local database.
- `SEATS_UNAVAILABLE`: another hold owns the seat; this is an expected `409`.
- Celery cannot connect: verify Redis database `1` is reachable.

Security and controlled outage procedures are documented in
`docs/security.md` and `docs/failure-testing.md`.

## Backend quick start

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
python run.py
```

The liveness endpoint is `http://localhost:5000/health/live`. Readiness is
`http://localhost:5000/health/ready` and returns HTTP 503 until PostgreSQL and
Redis are reachable.

To perform a read-only PostgreSQL connectivity check:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/check_postgres.py
```

## Frontend quick start

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Do not commit `.env` files. PostgreSQL and Redis installation instructions,
schema design, and milestone definitions are documented in the master plan.
