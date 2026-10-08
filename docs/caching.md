# Caching

The catalogue uses Redis cache-aside reads. On a cache hit, the API returns
the JSON value. On a miss, it reads PostgreSQL, stores the response, and then
returns it.

| Key | Data | TTL |
|---|---|---:|
| `catalogue:events:<query-string>` | paginated event list | 600 seconds |
| `catalogue:event:<id>` | event detail | 600 seconds |
| `catalogue:event:<id>:shows` | scheduled shows | 180 seconds |
| `catalogue:show:<id>:seats` | display-only seat map | 5 seconds |

Cache read/write/invalidation failures are logged and do not fail the request.
Hold, release, payment confirmation, cancellation, and expiration cleanup
delete the affected seat-map key after the database state changes.

Seat-map cache data can be stale briefly. Hold creation always locks and
revalidates PostgreSQL rows, so cache staleness cannot create a double booking.

