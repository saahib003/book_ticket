# Libraries and why they are used

## Backend

| Library | Role | Why this project uses it |
|---|---|---|
| Flask | HTTP application framework | Provides routing, request handling, application context, and the development server. |
| Flask-SQLAlchemy | Flask integration for SQLAlchemy | Connects the ORM session and engine to the application factory. |
| SQLAlchemy 2.x | ORM and SQL construction | Models relational entities and lets critical queries remain explicit, including row locks. |
| Psycopg 3 | PostgreSQL driver | Gives SQLAlchemy and direct scripts a PostgreSQL connection. |
| Alembic | Schema migrations | Records every database change as a repeatable, reviewable migration. |
| Pydantic | Input validation | Validates JSON bodies before business logic runs and produces predictable errors. |
| python-dotenv | Environment loading | Loads local `.env` configuration without putting secrets in source code. |
| Redis-py | Redis client | Stores TTL hints and is the transport for Celery; it is never the inventory authority. |
| Celery | Background task queue | Runs expiration cleanup and outbox processing outside HTTP requests. |
| Argon2-cffi | Password hashing | Uses a deliberately expensive password hash instead of storing credentials directly. |
| PyJWT | JWT encoding/decoding | Creates short-lived access tokens and refresh-token claims. Refresh sessions remain revocable in PostgreSQL. |
| Flask-Cors | Development CORS headers | Allows the Vite development origin to call the Flask API. This must be tightened for production. |
| Flask-SocketIO | WebSocket/Socket.IO server | Publishes low-latency seat-change notifications to clients in show rooms. |
| Pytest | Automated testing | Runs unit, integration, and later PostgreSQL concurrency tests. |
| Locust | Load testing | Generates repeatable browse, seat-map, hold, booking, and payment traffic and reports p50/p95/p99 latency. |

## Frontend

| Library | Role | Why this project uses it |
|---|---|---|
| React | UI component model | Renders the booking flow and keeps selection state explicit. |
| TypeScript | Static typing | Makes API response shapes and UI state easier to reason about. |
| Vite | Frontend dev server/build tool | Provides fast local development and production bundles. |
| TanStack Query | Planned server-state library | Will manage caching, refetching, and invalidation as the UI grows. |
| socket.io-client | Browser Socket.IO client | Reconnects to the API and triggers authoritative seat-map reloads after events. |
| Vitest | Planned frontend test runner | Will test components and API-state behavior. |

## Infrastructure images

| Image | Role | Why it is used locally |
|---|---|---|
| `postgres:18` | Relational database | Runs the authoritative inventory and booking database. |
| `redis:7-alpine` | Cache/broker | Runs the local Redis dependency with a small image footprint. |

## Important separation

Libraries improve access, validation, and throughput; they do not replace the
database invariant. PostgreSQL constraints and transactions decide whether a
seat is available. Redis, Celery, React state, and WebSocket messages are
supporting mechanisms.
