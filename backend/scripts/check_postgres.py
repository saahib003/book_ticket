"""Read-only PostgreSQL connectivity check for local setup."""

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is not set. Copy .env.example to .env first.")
database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

try:
    with psycopg.connect(database_url, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), version()")
            database, version = cursor.fetchone()
            print(f"PostgreSQL connection: ok ({database})")
            print(f"Server: {version.splitlines()[0]}")
except Exception as exc:
    print(f"PostgreSQL connection: failed ({exc.__class__.__name__}: {exc})")
    raise SystemExit(1)
