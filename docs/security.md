# Security controls

## Passwords and tokens

Argon2 hashes passwords. The API returns short-lived access JWTs and stores
only SHA-256 hashes of refresh tokens in PostgreSQL. Refresh tokens rotate on
use and logout revokes the stored session.

## Rate limits

The fixed-window limiter uses Redis counters:

- `rate:register:<client-ip>`: five requests per 60 seconds
- `rate:login:<client-ip>`: five requests per 60 seconds
- `rate:hold:user:<user-id>`: twenty requests per 60 seconds

Authentication answers “who is this?”; authorization answers “may this user
perform this action?” Admin catalogue writes use the authenticated user's
`role=ADMIN` value and return `403 ADMIN_REQUIRED` for ordinary customers.

`INCR` creates the counter and `EXPIRE` sets its window. A `429 RATE_LIMITED`
response means the limit was exceeded. The current implementation fails open
when Redis is unavailable because rate limiting is not allowed to change
PostgreSQL inventory correctness; production should add monitoring and decide
whether authentication limits should fail closed.

## Request and response protection

`MAX_CONTENT_LENGTH` defaults to 16 KiB. Responses include `nosniff`, `DENY`
frame protection, and a strict referrer policy. CORS is restricted to
`CORS_ORIGIN`, which is `http://localhost:5173` locally.

Before deployment, replace development secrets, use HTTPS, restrict CORS to
the real frontend origin, and remove secrets from all logs.
