# Error Codes Reference

All errors in SocketSpec are delivered to the client as `__error__` events with a structured payload:

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

---

## Error Code Catalog

### Authentication Errors

| Code | Trigger | Connection Impact |
|---|---|---|
| `AUTH_ERROR` | `AuthBackend.authenticate()` returned `None` at connect time | Connection closed (code 4001) |
| `AUTH_EXPIRED` | JWT expired during an active session | Connection closed |

### Validation Errors

| Code | Trigger | Connection Impact |
|---|---|---|
| `VALIDATION_ERROR` | Malformed JSON, missing `event` key, or Pydantic model validation failure | Connection remains open |
| `PAYLOAD_TOO_LARGE` | Inbound payload exceeds `max_payload_size` | Connection remains open |
| `UNKNOWN_EVENT` | No handler registered for the received event name | Connection remains open |

### Rate Limiting Errors

| Code | Trigger | Connection Impact |
|---|---|---|
| `RATE_LIMIT_ERROR` | Token bucket exhausted for this connection | Connection remains open; client may retry after tokens replenish |

### Handler Errors

| Code | Trigger | Connection Impact |
|---|---|---|
| `HANDLER_ERROR` | Unhandled exception in an event handler | Connection remains open |

### Permission Errors

| Code | Trigger | Connection Impact |
|---|---|---|
| `PERMISSION_ERROR` | Room guard returned `False` for a join attempt | Connection remains open |
| `ROOM_NOT_FOUND` | Broadcast or operation targeted a non-existent room | Connection remains open |

### Session Errors

| Code | Trigger | Connection Impact |
|---|---|---|
| `SESSION_EXPIRED` | `max_duration` limit reached | Connection closed |
| `IDLE_TIMEOUT` | No inbound messages within the configured `idle_timeout` | Connection closed |

---

## Error Envelope Fields

| Field | Type | Always Present | Description |
|---|---|---|---|
| `code` | `string` | Yes | Machine-readable error code from the catalog above |
| `event` | `string` | When applicable | The event name that triggered the error |
| `message` | `string` | Yes | Human-readable description |
| `request_id` | `string` | Yes | UUID for tracing and correlation |
| `details` | `object` | Yes | Additional context; may be empty |

---

## WebSocket Close Codes

When SocketSpec terminates a connection, it uses these WebSocket close codes:

| Code | Standard Name | SocketSpec Usage |
|---|---|---|
| `1000` | Normal Closure | Client or server initiates a clean disconnect |
| `1008` | Policy Violation | Connection rejected at the adapter level |
| `4001` | Authentication Failure | Custom: `AuthBackend.authenticate()` returned `None` |
| `4003` | Origin Forbidden | Custom: Origin header not in the allowed origins list |

---

## Handling Errors on the Client

### JavaScript Example

```javascript
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    if (msg.event === "__error__") {
        const error = msg.payload;

        switch (error.code) {
            case "VALIDATION_ERROR":
                console.error("Invalid payload:", error.message);
                break;
            case "RATE_LIMIT_ERROR":
                console.warn("Rate limited. Backing off.");
                break;
            case "PERMISSION_ERROR":
                console.warn("Access denied:", error.message);
                break;
            default:
                console.error("Server error:", error.code, error.message);
        }
    }
};
```

### Python TestClient Example

```python
from socketspec.testing import TestClient

async def test_validation_error():
    client = TestClient(socket)
    async with client.connect() as conn:
        await conn.emit("send_message", {"invalid": "payload"})
        error = await conn.receive("__error__")
        assert error["code"] == "VALIDATION_ERROR"
```
