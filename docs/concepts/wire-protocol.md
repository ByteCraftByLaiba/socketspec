# Wire Protocol

All communication between clients and SocketSpec uses a simple JSON envelope format over WebSocket text frames. This page documents the complete wire protocol specification.

---

## Message Envelope

Every message -- both client-to-server and server-to-client -- follows this structure:

```json
{
    "event": "<event_name>",
    "payload": { ... }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | `string` | Yes | The event name. Must match a registered handler (client-to-server) or a known system event. |
| `payload` | `object` | Yes | The event data. Structure depends on the event. Can be an empty object `{}`. |

Messages that do not conform to this structure receive a `VALIDATION_ERROR` response.

---

## Client-to-Server Messages

### User Events

Clients send events to invoke registered handlers:

```json
{
    "event": "send_message",
    "payload": {
        "room": "general",
        "text": "Hello, everyone!"
    }
}
```

The `payload` is validated against the Pydantic model registered for the event. If validation fails, the server responds with a `VALIDATION_ERROR` and the handler is never called.

### System Events

| Event | Payload | Description |
|---|---|---|
| `__pong__` | `{}` | Response to a server heartbeat ping. Handled internally; never routed to user handlers. |
| `__refresh_auth__` | `{}` | Client requests a token refresh. |

---

## Server-to-Client Messages

### User Events

Handlers emit events back to clients using `conn.emit()` or `rooms.broadcast()`:

```json
{
    "event": "new_message",
    "payload": {
        "from": "conn_abc123",
        "text": "Hello, everyone!"
    }
}
```

### System Events

SocketSpec emits the following system events automatically:

| Event | Payload | When |
|---|---|---|
| `__connect__` | `{"conn_id": "..."}` | Immediately after a connection is established and authenticated |
| `__disconnect__` | `{"reason": "..."}` | Before the server closes the connection |
| `__ping__` | `{}` | Heartbeat probe sent at the configured interval |
| `__error__` | Error envelope (see below) | Any error condition |
| `__auth_expiring__` | `{"expires_in": <seconds>}` | JWT is approaching expiry (within the configured refresh window) |
| `__session_expiring__` | `{"expires_in": <seconds>}` | Session max duration is approaching |
| `__idle_warning__` | `{}` | Connection has been idle beyond the configured threshold |
| `__server_shutdown__` | `{}` | Server is initiating graceful shutdown |

---

## Error Envelope

All errors are delivered as `__error__` events with a structured payload:

```json
{
    "event": "__error__",
    "payload": {
        "code": "VALIDATION_ERROR",
        "event": "send_message",
        "message": "Invalid message format",
        "request_id": "a3f9bc12-...",
        "details": {}
    }
}
```

| Field | Type | Description |
|---|---|---|
| `code` | `string` | Machine-readable error code. See [Error Codes Reference](../reference/errors.md). |
| `event` | `string` | The event name that triggered the error (if applicable). |
| `message` | `string` | Human-readable error description. |
| `request_id` | `string` | Unique identifier for tracing. |
| `details` | `object` | Additional context (validation field errors, rate limit retry-after, etc.). |

---

## WebSocket Close Codes

SocketSpec uses the following close codes when terminating connections:

| Code | Meaning | When Used |
|---|---|---|
| `1000` | Normal closure | Client or server initiates a clean disconnect |
| `1008` | Policy violation | Connection rejected at the adapter level (e.g., missing auth when no backend-specific code applies) |
| `4001` | Authentication failure | `AuthBackend.authenticate()` returned `None` |
| `4003` | Origin forbidden | Origin header did not match the allowed origins list |

---

## Transport Requirements

- All messages must be sent as WebSocket **text frames** containing valid JSON.
- Binary frames are not supported and will be silently dropped.
- Maximum payload size defaults to 64 KB and is configurable via `SocketApp(max_payload_size=...)`.
