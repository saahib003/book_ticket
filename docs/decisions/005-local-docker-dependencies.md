# ADR 005: Use Docker Desktop for local PostgreSQL and Redis dependencies

## Decision

For the accelerated two-day implementation, Docker Desktop provides only the
local PostgreSQL and Redis dependencies. Flask, React, and Celery remain
native processes.

## Rationale

The planned native PostgreSQL service is available, but a Redis-compatible
native service is not. Project-managed containers provide reproducible ports,
credentials, health checks, and persistent local volumes without putting the
application in a container.

## Consequence

Local setup differs from the original no-Docker constraint and uses more
laptop resources. The application remains portable because all dependency
connections are environment-configured. AWS deployment decisions remain
separate.

