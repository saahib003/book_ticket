# ADR 001: Start with a modular monolith

## Decision

Build one Flask application with clear domain module boundaries before
considering service extraction.

## Rationale

The booking workflow needs simple transaction boundaries while we learn
concurrency, idempotency, and failure handling. A monolith makes those
boundaries visible and avoids premature distributed-systems complexity.

## Consequence

Modules must keep business logic out of HTTP routes so future extraction
remains possible.

