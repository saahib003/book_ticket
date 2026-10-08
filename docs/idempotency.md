# Idempotency

Hold creation requires an `Idempotency-Key`. The database stores the user,
operation, key, request hash, status code, and response JSON.

- Repeating the same key and request returns the original response.
- Reusing a key with a different request returns `409 IDEMPOTENCY_KEY_REUSED`.
- A unique database constraint protects the key scope when requests race.

The Redis hold key is only a five-minute TTL hint and is written after the
database transaction commits.

