# Architecture

The project starts as a Flask modular monolith with a React frontend.
PostgreSQL is the authoritative store for inventory and booking state. Redis
is used for cache, TTL hints, rate limits, Celery transport, and WebSocket
coordination; it never owns seat correctness.

Local development uses native Windows services. Docker is reserved for the
later AWS deployment milestone.

