# API Reference: Connection

::: socketspec.connection.Connection

---

## Attributes

| Attribute | Type | Description |
|---|---|---|
| `id` | `str` | Unique connection ID (UUID4) |
| `identity` | `Identity` | Authenticated identity (user_id, role, token_expires_at) |
| `session` | `SessionInfo` | Session metadata (started_at, expires_at) |
| `connected_at` | `datetime` | UTC timestamp of connection establishment |
| `last_active` | `datetime` | UTC timestamp of last received event (updated on every inbound message) |
| `rooms` | `set[str]` | Room names this connection is currently in |
| `headers` | `dict[str, str]` | HTTP upgrade request headers |
| `query_params` | `dict[str, str]` | HTTP upgrade request query parameters |
| `namespace` | `str` | The namespace this connection belongs to |

---

## Methods

### `await conn.emit(event, payload)`

Send a message directly to this connection.

```python
await conn.emit("notification", {"text": "You have a new message"})
```

| Parameter | Type | Description |
|---|---|---|
| `event` | `str` | Event name |
| `payload` | `dict` | JSON-serializable payload |

### `await conn.disconnect(reason)`

Close this connection gracefully.

```python
await conn.disconnect("banned")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `reason` | `str` | `"server_close"` | Reason string logged and passed to `on_disconnect` hooks |

---

## Identity

`conn.identity` is populated by the `AuthBackend` at connect time.

```python
@dataclass
class Identity:
    user_id: str | None = None
    role: str | None = None
    token_expires_at: datetime | None = None
    extra: dict = field(default_factory=dict)
```

For unauthenticated connections (no `auth=` configured), all fields are `None`.

Access identity in a handler:

```python
@socket.on("protected_action")
async def protected(conn, payload) -> None:
    if not conn.identity.user_id:
        await conn.emit("__error__", {"code": "AUTH_ERROR"})
        return
    # proceed
```

---

## SessionInfo

`conn.session` contains timing metadata for the current session.

```python
@dataclass
class SessionInfo:
    started_at: datetime       # when the connection was established
    expires_at: datetime | None  # absolute expiry (None = no max_duration)
    token_expires_at: datetime | None  # from identity
```

---

## Usage in Handlers

```python
from socketspec.connection import Connection

@socket.on("whoami")
async def whoami(conn: Connection) -> None:
    await conn.emit("identity", {
        "conn_id":    conn.id,
        "user_id":    conn.identity.user_id,
        "rooms":      list(conn.rooms),
        "connected":  conn.connected_at.isoformat(),
        "last_active": conn.last_active.isoformat(),
    })
```

---

## Usage in Lifecycle Hooks

```python
@socket.on_connect
async def on_connect(conn: Connection) -> None:
    # Send a welcome message immediately after connect
    await conn.emit("welcome", {
        "conn_id": conn.id,
        "message": "Connected to SocketSpec",
    })

@socket.on_disconnect
async def on_disconnect(conn: Connection, reason: str) -> None:
    # Log disconnect reason
    logger.info("Client %s disconnected: %s", conn.id, reason)
```
