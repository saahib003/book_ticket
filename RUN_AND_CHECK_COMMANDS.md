# Run and check commands

This is the practical command sheet for running the ticket-booking learning
project on Windows PowerShell. Run commands from the directory shown in each
section. Use separate terminals for long-running API, frontend, and Celery
processes.

## 1. Project directory

```powershell
cd D:\saavran\padhaii\System_Design
```

The project uses Docker Desktop only for PostgreSQL and Redis. The API,
frontend, and worker run natively on Windows.

## 2. Start PostgreSQL and Redis

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"

& $docker start ticket-booking-postgres
& $docker start ticket-booking-redis
& $docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected: both `ticket-booking-postgres` and `ticket-booking-redis` show
`Up`.

Check PostgreSQL directly:

```powershell
& $docker exec ticket-booking-postgres pg_isready -U ticket_app -d ticket_booking
```

Expected: `accepting connections`.

Check Redis directly:

```powershell
& $docker exec ticket-booking-redis redis-cli ping
```

Expected: `PONG`.

## 3. Apply migrations and seed data

```powershell
cd D:\saavran\padhaii\System_Design\backend

.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe scripts\seed_catalogue.py
.\.venv\Scripts\python.exe scripts\seed_load_test_show.py
```

Expected:

- Alembic reports the database is current.
- Normal catalogue seed reports no unnecessary changes.
- Load-test seed reports show ID `2` and its available seat count.

Show seat counts:

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker exec ticket-booking-postgres psql -U ticket_app -d ticket_booking -c "SELECT show_id, status, count(*) FROM show_seats GROUP BY show_id, status ORDER BY show_id, status;"
```

Use show ID `1` for the normal demo and show ID `2` for load experiments.

## 4. Start the API

Terminal 1:

```powershell
cd D:\saavran\padhaii\System_Design\backend
.\.venv\Scripts\python.exe run.py
```

Leave this terminal open. The API uses port `5000`.

Check liveness:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health/live -UseBasicParsing
```

Expected HTTP status: `200`.

Check readiness:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health/ready -UseBasicParsing
```

Expected HTTP status: `200`, with PostgreSQL and Redis marked `ok`.

View metrics:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/metrics -UseBasicParsing
```

Look for `ticket_booking_http_requests_total` and
`ticket_booking_cache_operations_total`.

## 5. Start the frontend

Terminal 2:

```powershell
cd D:\saavran\padhaii\System_Design\frontend
npm run dev -- --host=127.0.0.1
```

Open this URL manually:

```text
http://127.0.0.1:5173/
```

Expected UI flow:

1. Events appear.
2. Search filters events.
3. Selecting an event shows showtimes.
4. Selecting a show displays seats.
5. Register or sign in.
6. Select available seats.
7. Hold the seats.
8. Observe the countdown.
9. Pay and confirm.
10. View the booking in history.

## 6. Start Celery

Terminal 3:

```powershell
cd D:\saavran\padhaii\System_Design\backend
\.venv\Scripts\celery.exe -A celery_worker.celery worker --loglevel=INFO --pool=solo
```

Expected registered tasks include:

- `holds.cleanup_expired`
- `outbox.process_pending`

## 7. Run all automated tests

Backend:

```powershell
cd D:\saavran\padhaii\System_Design\backend
\.venv\Scripts\python.exe -m pytest -q
```

Expected currently: `27 passed`.

Frontend:

```powershell
cd D:\saavran\padhaii\System_Design\frontend
npm test
npm run build
```

Expected currently: `3 tests passed` and a successful Vite build.

## 8. Check the API manually

List events:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/v1/events | ConvertTo-Json -Depth 5
```

List shows for event 1:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/v1/events/1/shows | ConvertTo-Json -Depth 8
```

View the normal demo seat map:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/v1/shows/1/seats | ConvertTo-Json -Depth 6
```

## 9. Run the hot-seat concurrency test

This sends 100 competing hold attempts for one seat. It uses show 2 and
temporarily selected seat ID `11` by default for the isolated experiment.

```powershell
cd D:\saavran\padhaii\System_Design\backend

$env:LOAD_SHOW_ID = "2"
$env:LOAD_SHOW_SEAT_ID = "11"
.\.venv\Scripts\python.exe scripts\concurrency_hold_test.py
```

Expected:

```text
winners=1 conflicts=99 unexpected=0
```

This proves PostgreSQL locking prevents double ownership.

## 10. Run Locust load testing

Use the isolated show. Start the API first.

```powershell
cd D:\saavran\padhaii\System_Design

$env:LOAD_SHOW_ID = "2"
.\backend\.venv\Scripts\python.exe -m locust `
  -f .\load-tests\locustfile.py `
  --headless `
  -u 3 `
  -r 1 `
  -t 30s `
  --host http://127.0.0.1:5000 `
  --csv .\load-tests\local-run
```

Meaning of options:

- `-u 3`: three concurrent virtual users.
- `-r 1`: add one user per second.
- `-t 30s`: stop after thirty seconds.
- `--csv`: save repeatable result files.

Observe request count, error count, throughput, p50, p95, and p99. Expected
seat conflicts are classified as business outcomes rather than infrastructure
failures.

## 11. View performance metrics during load

While API and Locust are running:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/metrics -UseBasicParsing |
  Select-Object -ExpandProperty Content |
  Select-String "ticket_booking_http_requests_total|ticket_booking_cache_operations_total"
```

Repeat a catalogue request and compare cold versus warm cache behavior:

```powershell
$query = "metrics-probe-$(Get-Random)"
$uri = "http://127.0.0.1:5000/api/v1/events?search=$query"
Measure-Command { Invoke-WebRequest $uri -UseBasicParsing | Out-Null }
Measure-Command { Invoke-WebRequest $uri -UseBasicParsing | Out-Null }
```

The second request should usually be faster because the first request populated
Redis cache.

## 12. Check database query plans

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker exec ticket-booking-postgres psql -U ticket_app -d ticket_booking -c "EXPLAIN (ANALYZE, BUFFERS) SELECT id, show_id, seat_id, status FROM show_seats WHERE show_id = 2 ORDER BY seat_id;"
```

Look for:

- Scan type: sequential scan or index scan.
- Planning time.
- Execution time.
- Buffer hits and reads.

## 13. Redis failure experiment

Do not run this while another person is using the project.

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker stop ticket-booking-redis
```

Check readiness:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health/ready -UseBasicParsing
```

Expected: HTTP `503` because Redis is unavailable.

Check liveness:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health/live -UseBasicParsing
```

Expected: HTTP `200` because the Flask process is still alive.

Restart Redis immediately:

```powershell
& $docker start ticket-booking-redis
```

Expected: readiness returns to `200`.

## 14. PostgreSQL failure experiment

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker stop ticket-booking-postgres
```

Expected:

- `/health/live` returns `200`.
- `/health/ready` returns `503`.
- Database-backed API operations return `503 DEPENDENCY_UNAVAILABLE`.

Restart PostgreSQL:

```powershell
& $docker start ticket-booking-postgres
```

Wait a few seconds, then check:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health/ready -UseBasicParsing
```

## 15. Stop the local runtime

Stop API, frontend, and Celery with `Ctrl+C` in their terminals.

Then stop dependencies:

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker stop ticket-booking-postgres
& $docker stop ticket-booking-redis
```

Stopping containers does not delete their named volumes or database data.

## 16. Troubleshooting

Port 5000 already in use:

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen
```

Port 5173 already in use:

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen
```

Readiness returns `503`:

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker ps
& $docker exec ticket-booking-postgres pg_isready -U ticket_app -d ticket_booking
& $docker exec ticket-booking-redis redis-cli ping
```

Frontend cannot reach API:

- Confirm API is running on port `5000`.
- Confirm frontend is running on port `5173`.
- Check browser developer-console errors.
- Confirm `frontend/.env` uses the expected API URL.

Do not run `docker volume rm` unless you intentionally want to erase the local
database and Redis data.
