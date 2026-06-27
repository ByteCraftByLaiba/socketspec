# How-to: Mount on FastAPI

This guide covers every option available when mounting SocketSpec on a FastAPI
application.

---

## Basic Mount

```python
from fastapi import FastAPI
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount

socket = SocketApp()
app = FastAPI()
mount(socket, app, path="/ws")
```

Clients connect to `ws://host/ws`.

---

## With the Docs UI

```python
socket = SocketApp(
    docs=True,
    docs_url="/socket-docs",          # URL to serve the UI
    docs_access_token="secret-token", # optional — protects the docs page
)
```

The access token can be passed as:
- `Authorization: Bearer secret-token` header
- `?token=secret-token` query parameter

---

## Authentication

```python
from socketspec.security.auth import JWTAuth

socket = SocketApp(
    auth=JWTAuth(secret="your-jwt-secret", algorithm="HS256"),
)
```

The JWT is expected in:
- `Authorization: Bearer <token>` header
- `?token=<token>` query parameter

On failure, SocketSpec closes the connection with code `4001` and sends
`{"code": "AUTH_ERROR"}` before closing.

For API keys:

```python
from socketspec.security.auth import APIKeyAuth

socket = SocketApp(
    auth=APIKeyAuth(valid_keys={"key-abc", "key-xyz"}),
)
```

---

## Rate Limiting

```python
from socketspec.security.ratelimit import RateLimit

socket = SocketApp(
    rate_limit=RateLimit(rate=10, capacity=20),  # 10 events/sec, burst of 20
)
```

---

## Origin Validation

```python
socket = SocketApp(
    allowed_origins=["https://myapp.com", "https://staging.myapp.com"],
)
```

Use `["*"]` (the default) to allow all origins.

---

## Session Configuration

```python
from socketspec.session import SessionConfig

socket = SocketApp(
    session=SessionConfig(
        max_duration=3600,        # max session length in seconds
        idle_timeout=300,         # disconnect after 5 min of inactivity
        heartbeat_interval=25,    # ping every 25 seconds
        heartbeat_timeout=10,     # disconnect if pong not received in 10s
        token_refresh_window=60,  # warn 60s before token expires
    ),
)
```

---

## Lifecycle Hooks

```python
from socketspec.connection import Connection

@socket.on_connect
async def on_connect(conn: Connection) -> None:
    print(f"Connected: {conn.id}")

@socket.on_disconnect
async def on_disconnect(conn: Connection, reason: str) -> None:
    print(f"Disconnected: {conn.id} ({reason})")

@socket.on_error
async def on_error(conn: Connection, error: Exception) -> None:
    print(f"Handler error on {conn.id}: {error}")
```

---

## Complete Example

```python
from fastapi import FastAPI
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount
from socketspec.security.auth import JWTAuth
from socketspec.security.ratelimit import RateLimit
from socketspec.session import SessionConfig

socket = SocketApp(
    docs=True,
    docs_url="/socket-docs",
    auth=JWTAuth(secret="super-secret", algorithm="HS256"),
    allowed_origins=["https://myapp.com"],
    rate_limit=RateLimit(rate=20, capacity=50),
    session=SessionConfig(max_duration=7200, idle_timeout=300),
    namespace="/",
)

app = FastAPI(title="My WebSocket API")
mount(socket, app, path="/ws")
```
