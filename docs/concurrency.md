# Concurrency

Hold creation uses PostgreSQL row-level pessimistic locking. Requested
`show_seats` IDs are deduplicated and sorted before `SELECT ... FOR UPDATE`.
Every requested seat must be available while its rows are locked; otherwise
the whole transaction rolls back.

Redis stores only a best-effort `hold:{hold_id}` TTL hint. A missing or stale
Redis key cannot permit double booking because the database owns seat state.

Run the live experiment from `backend/` while Flask is running:

```powershell
.\.venv\Scripts\python.exe scripts/concurrency_hold_test.py
```

The expected result is 100 attempts, exactly one winner, 99 conflicts, and no
unexpected responses. The script releases the winning hold after measuring it.
