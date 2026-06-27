# Tutorial: Your First Event

This tutorial walks through every part of a SocketSpec event handler —
from registration to client connection to response.

---

## What We're Building

A simple echo server. The client sends `{"echo": "hello"}` and the server
sends back `{"echo": "hello", "from": "<connection_id>"}`.

---

## Step 1 — Register the Event

```python
from fastapi import FastAPI
from pydantic import BaseModel
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount

socket = SocketApp(docs=True)

class EchoPayload(BaseModel):
    echo: str

@socket.on(
    "echo",
    description="Echo a message back to the sender.",
    tags=["demo"],
)
async def echo_handler(conn, payload: EchoPayload) -> None:
    await conn.emit("echo_response", {
        "echo": payload.echo,
        "from": conn.id,
    })

app = FastAPI()
mount(socket, app, path="/ws")
```

### What `@socket.on` does

`@socket.on("echo")` registers the handler with the `EventRegistry`.
At startup (before the first connection), SocketSpec validates that:

- No two handlers share the same event name in the same namespace
- The event name is not a reserved system event (like `__ping__`)

### The handler signature

```python
async def handler(conn: Connection, payload: YourModel) -> None:
```

- **`conn`** — the `Connection` object for this client. Use it to `emit()` back,
  check `conn.identity`, or join rooms.
- **`payload`** — automatically parsed and validated by Pydantic. If validation
  fails, SocketSpec sends `{"event": "__error__", "payload": {"code": "VALIDATION_ERROR"}}`
  to the client and does **not** call your handler.

---

## Step 2 — Connect from the Docs UI

1. Start the server: `uvicorn main:app --reload`
2. Open http://localhost:8000/socket-docs
3. Click **Connect** — the status bar shows 🟢 Connected
4. Find the **echo** card under the **demo** tag group
5. Click it to expand — you'll see the payload schema table:

| Name | Type   | Required | Description |
|------|--------|----------|-------------|
| echo | string | ✓        |             |

6. Click **Try it out**, set `{"echo": "hello world"}`, click **▶ Send Event**
7. The response `{"event": "echo_response", ...}` appears inline

---

## Step 3 — Connect from JavaScript

```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
    ws.send(JSON.stringify({
        event: "echo",
        payload: { echo: "hello world" }
    }));
};

ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    console.log(msg); // { event: "echo_response", payload: { echo: "hello world", from: "..." } }
};
```

All messages follow the envelope format: `{ "event": "<name>", "payload": { ... } }`.

---

## Step 4 — Write a Test

```python
import pytest
from socketspec.testing import TestClient

@pytest.mark.asyncio
async def test_echo():
    async with TestClient(socket) as client:
        conn = await client.connect()
        await conn.send("echo", {"echo": "hello world"})
        response = await conn.receive()

        assert response["event"] == "echo_response"
        assert response["payload"]["echo"] == "hello world"
        assert "from" in response["payload"]
```

`TestClient` runs the full SocketSpec stack in-process — security layers,
middleware, DI, session management — without a real network socket.

---

## What Happens on Each Inbound Message

```
Client sends JSON
    │
    ▼
Payload size check  ──▶ PAYLOAD_TOO_LARGE error
    │
    ▼
JSON parse          ──▶ VALIDATION_ERROR error
    │
    ▼
Rate limit check    ──▶ RATE_LIMIT_ERROR error
    │
    ▼
touch() last_active
    │
    ▼
__pong__ early exit (system frame, not routed)
    │
    ▼
Middleware chain
    │
    ▼
Pydantic validation ──▶ VALIDATION_ERROR error
    │
    ▼
DI resolution
    │
    ▼
Your handler
```

Handler exceptions are caught and emitted as `HANDLER_ERROR` — they never
crash the connection.

---

## Next

- [Payload Validation](payload-validation.md) — constraints, nested models, custom errors
- [Rooms](rooms.md) — broadcasting to groups of connections
