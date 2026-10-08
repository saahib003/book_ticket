# Database migrations

Alembic migrations live in `versions/`. Shared schemas must be changed through
migrations, never by manual production edits.

From `backend/`, create a migration after models exist with:

```powershell
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

The migration environment reads the Flask application configuration, so it
uses the same `DATABASE_URL` as the API.
