# Database

The first migration, `0001_create_auth_tables`, creates `users` and
`refresh_tokens`. PostgreSQL is the production and integration-test source of
truth. The current unit tests use an in-memory SQLite database only to test
HTTP and hashing behavior quickly; concurrency tests must use PostgreSQL.

Apply migrations from `backend/` with:

```powershell
alembic upgrade head
```

Authentication stores Argon2 password hashes and SHA-256 hashes of refresh
tokens. A refresh token is rotated and revoked when used.

Migration `0002_create_catalogue_tables` adds venues, auditoriums, physical
seats, events, and shows. Seat availability is intentionally not stored on
`seats`; show-specific inventory will be added as `show_seats` later.
