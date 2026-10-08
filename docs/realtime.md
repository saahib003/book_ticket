# Real-time seat updates

Flask-SocketIO creates a room named `show:<show_id>`. A browser emits
`join_show` after connecting. Inventory changes emit:

```json
{
  "type": "SEAT_STATUS_CHANGED",
  "show_id": 1,
  "seat_ids": [1, 2],
  "status": "HELD",
  "seat_map_version": 3
}
```

The frontend treats this as an invalidation signal and reloads
`GET /shows/{id}/seats`. It does not apply the event as authoritative state.
On reconnect, or when a future version-gap check detects missed events, the
client must reload the complete seat map. Redis is used for Socket.IO
coordination, not seat ownership.

## Local server command

Run `python run.py` from `backend/`. This entry point calls
`socketio.run(...)`, which supports the Socket.IO handshake and WebSocket or
long-polling transport. The normal Flask development command is suitable for
HTTP-only checks but is not the documented realtime server.
