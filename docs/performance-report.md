# Performance comparison report

These are local learning measurements, not production capacity guarantees.
Every number includes its workload and data condition so it can be reproduced.

## Results collected on 2026-09-02

| Experiment | Workload | Result | Meaning |
|---|---|---:|---|
| Cache cold | One unique catalogue query | ~211 ms | Redis miss, PostgreSQL read, Redis write |
| Cache warm | Repeat of the same query | ~14 ms | Redis hit avoided the database read |
| Locust baseline | 3 users, 1/sec ramp, 10 sec | 49 requests, 0% measured failures; p50 6 ms, p95 74 ms, p99 150 ms | Browse/seat/hold contention baseline |
| Full booking load | 3 users, 1/sec ramp, 15 sec | 82 requests, 0% measured failures; p50 25 ms, p95 160 ms, p99 210 ms | Included booking, payment, and confirmation |
| Hot seat | 100 concurrent attempts for one seat | 1 winner, 99 conflicts, 0 unexpected responses, 991.6 ms | Database locking preserved the invariant |

Expected `409 SEATS_UNAVAILABLE` responses are business outcomes, not load
test failures. The Locust harness explicitly classifies them that way.

## Database plan comparison

The event query uses `ix_events_status`. The seat query now has
`ix_show_seats_show_id_seat_id`, added by migration `0007`. PostgreSQL still
selected a sequential scan plus sort for the 100-seat local show because
scanning a tiny table is cheaper than an index lookup. This is an important
lesson: adding an index does not force the optimizer to use it, and the plan
must be measured at realistic table sizes.

Inspect plans with:

```powershell
$docker = "C:\Users\lenovo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
& $docker exec ticket-booking-postgres psql -U ticket_app -d ticket_booking -c "EXPLAIN (ANALYZE, BUFFERS) SELECT id, show_id, seat_id, status FROM show_seats WHERE show_id = 2 ORDER BY seat_id;"
```

## Current conclusions

- Cache-aside materially reduces repeated catalogue latency in this local run.
- PostgreSQL locking is the correctness bottleneck by design for a hot seat;
  Redis is not used to decide ownership.
- The booking flow completed successfully under the small mixed workload.
- Worker-count comparison is not yet meaningful on this laptop; it requires a
  longer fixed workload and a controlled Celery task volume.
- Larger, repeatable runs should use a resettable database and record pool
  size, CPU, memory, worker count, cache state, and data volume.
