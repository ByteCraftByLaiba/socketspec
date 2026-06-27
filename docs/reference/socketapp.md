# API Reference: SocketApp

::: socketspec.app.SocketApp

---

## Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `docs` | `bool` | `False` | Enable the `/socket-docs` interactive UI |
| `docs_url` | `str` | `"/socket-docs"` | URL path for the docs UI |
| `docs_access_token` | `str \| None` | `None` | Bearer token required to access the docs UI |
| `auth` | `AuthBackend \| None` | `None` | Authentication backend (JWTAuth, APIKeyAuth, or custom) |
| `backend` | `"memory" \| BackendAdapter` | `"memory"` | Storage backend for connections and rooms |
| `allowed_origins` | `list[str] \| None` | `["*"]` | Allowed WebSocket origin headers |
| `max_payload_size` | `int` | `65536` | Maximum inbound payload size in bytes |
| `rate_limit` | `RateLimit \| None` | `None` | Token bucket rate limit per connection |
| `session` | `SessionConfig \| None` | `SessionConfig()` | Heartbeat and TTL configuration |
| `rooms` | `list[Room] \| None` | `None` | Static rooms to create at startup |
| `namespace` | `str` | `"/"` | Namespace prefix for all events |

---

## Event Registration

### `@socket.on(event, *, ...)`

Register an event handler.

```python
@socket.on(
    "send_message",
    description="Send a chat message.",
    tags=["chat"],
    emits=[Emits("message_ack", model=AckModel)],
    broadcasts=[Broadcasts("new_message", room="chat:{room}", model=MsgModel)],
    ordered=False,
    deprecated=False,
)
async def handler(conn: Connection, payload: MyModel) -> None: ...
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `event` | `str` | — | Event name. Cannot be a reserved system event. |
| `description` | `str` | `""` | Shown in the docs UI |
| `tags` | `list[str]` | `[]` | Group events in the docs UI |
| `emits` | `list[Emits]` | `[]` | Metadata: events the handler emits back to sender |
| `broadcasts` | `list[Broadcasts]` | `[]` | Metadata: events the handler broadcasts to rooms |
| `ordered` | `bool` | `False` | If True, events from this connection are processed sequentially |
| `deprecated` | `bool` | `False` | Shows ⚠ DEPRECATED badge in the docs UI |

---

## Lifecycle Decorators

### `@socket.on_connect`
Runs after a connection is established. Receives `conn: Connection`.

### `@socket.on_disconnect`
Runs after a connection closes. Receives `conn: Connection, reason: str`.

### `@socket.on_error`
Runs when a handler raises an unhandled exception. Receives `conn: Connection, error: Exception`.

### `@socket.on_room_join`
Runs after a connection joins a room. Receives `conn: Connection, room: str`.

### `@socket.on_room_leave`
Runs after a connection leaves a room. Receives `conn: Connection, room: str`.

### `@socket.room_guard(pattern)`
Register a room permission guard for a name pattern.

```python
@socket.room_guard("admin:{section}")
async def guard(conn: Connection, section: str) -> bool:
    return conn.identity.role == "admin"
```

### `@socket.middleware`
Register middleware that wraps every event handler.

```python
@socket.middleware
async def log_events(conn, event, payload, next_handler):
    print(f"[{conn.id}] {event}")
    await next_handler(conn, event, payload)
```

---

## System Events (Reserved)

These events are used internally. You cannot register handlers for them.

| Event | Direction | Description |
|---|---|---|
| `__connect__` | Server → Client | Connection established |
| `__disconnect__` | Server → Client | Connection closing |
| `__ping__` | Server → Client | Heartbeat ping |
| `__pong__` | Client → Server | Heartbeat response |
| `__error__` | Server → Client | Error envelope |
| `__auth_expiring__` | Server → Client | JWT near expiry |
| `__session_expiring__` | Server → Client | Session max-duration reached |
| `__idle_warning__` | Server → Client | Idle timeout reached |
| `__server_shutdown__` | Server → Client | Server is shutting down |
| `__refresh_auth__` | Client → Server | Client requests token refresh |

---

## Error Codes

All errors are delivered in the `__error__` envelope:

```json
{
  "event": "__error__",
  "payload": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "request_id": "uuid",
    "details": {}
  }
}
```

| Code | Trigger |
|---|---|
| `AUTH_ERROR` | Authentication failed at connect time |
| `AUTH_EXPIRED` | JWT expired mid-session |
| `HANDLER_ERROR` | Unhandled exception in event handler |
| `IDLE_TIMEOUT` | Connection was idle too long |
| `PAYLOAD_TOO_LARGE` | Payload exceeded `max_payload_size` |
| `PERMISSION_ERROR` | Room guard returned `False` |
| `RATE_LIMIT_ERROR` | Token bucket exhausted |
| `ROOM_NOT_FOUND` | Broadcast to a non-existent room |
| `SESSION_EXPIRED` | `max_duration` reached |
| `UNKNOWN_EVENT` | No handler registered for this event |
| `VALIDATION_ERROR` | JSON parse failure or Pydantic validation failure |
