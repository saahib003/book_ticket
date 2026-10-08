# Testing

Run backend tests from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The current suite covers liveness, readiness failure reporting, registration,
duplicate registration, login, protected profile access, invalid credentials,
refresh-token rotation, logout revocation, seat-hold atomicity, booking and
payment idempotency, webhook duplicates, cancellation, background jobs,
security failures, and Socket.IO room membership. The 100-request live
contention experiment is documented in `docs/load-testing.md`.
