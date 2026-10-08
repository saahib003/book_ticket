# ADR 002: PostgreSQL is the source of truth

## Decision

PostgreSQL owns inventory, holds, bookings, payments, and audit history.

## Rationale

Relational constraints and row-level transactions are required to prevent
double booking under concurrent requests. Redis failures must not compromise
correctness.

