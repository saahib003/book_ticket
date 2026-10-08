# ADR 006: Keep security controls separate from inventory correctness

## Decision

Use Redis for rate-limit counters and TTL hints, but keep PostgreSQL
transactions and constraints responsible for seat correctness.

## Rationale

Redis is fast and suitable for short-lived counters. It can restart or become
unavailable, so it cannot be the authority for holds, bookings, or payments.

## Consequence

The current limiter fails open during Redis outage and logs the condition.
This preserves availability but requires production monitoring and a deliberate
fail-closed decision for sensitive authentication endpoints.

