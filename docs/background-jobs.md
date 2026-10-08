# Background jobs

Celery Beat schedules `holds.cleanup_expired` every 30 seconds. The task
claims up to 100 expired active holds using PostgreSQL `FOR UPDATE SKIP LOCKED`,
releases their held show seats, increments seat versions, and marks the holds
`EXPIRED` in one transaction.

Run locally from `backend/`:

```powershell
.\.venv\Scripts\celery.exe -A celery_worker.celery worker --loglevel=INFO --pool=solo
.\.venv\Scripts\celery.exe -A celery_worker.celery beat --loglevel=INFO
```

The Windows `solo` pool is for learning only. Linux deployment will use
Celery’s normal worker pool. Redis transports the task; PostgreSQL remains the
authority for expiration and seat state.

The outbox worker task `outbox.process_pending` claims pending events with the
same batch-and-lock approach. Confirmation and cancellation events create
simulated notification rows idempotently, then mark the outbox event processed.
Repeated delivery is safe because notification rows have a unique event ID.
