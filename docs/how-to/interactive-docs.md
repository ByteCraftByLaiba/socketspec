# Interactive Documentation (`/socket-docs`)

SocketSpec includes a built-in interactive documentation UI for WebSocket APIs. It serves the same purpose as Swagger UI does for REST APIs: a browsable, testable catalog of every event your application handles, generated automatically from your code.

This is the primary testing and debugging interface for SocketSpec applications. Frontend engineers, QA teams, and API consumers can explore event schemas, inspect payload constraints, and trigger real-time WebSocket events directly from their browser without writing custom client code.

---

## Enabling the Documentation UI

Pass `docs=True` when creating your `SocketApp`:

```python
from fastapi import FastAPI
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount

socket = SocketApp(
    docs=True,                      # Enable the documentation UI
    docs_url="/socket-docs",        # URL path (default: /socket-docs)
    docs_access_token="my-secret",  # Optional: require a token to access
    debug=True,                     # Optional: enable live debug streaming
)

app = FastAPI()
mount(socket, app)
```

After starting the server, navigate to `http://localhost:8000/socket-docs`.

---

## Securing Access

In production, protect the documentation UI with an access token to prevent unauthorized access:

```python
socket = SocketApp(
    docs=True,
    docs_access_token="your-secret-token",
)
```

Authentication is accepted through two methods:

- **Query parameter**: `http://localhost:8000/socket-docs?token=your-secret-token`
- **Authorization header**: `Authorization: Bearer your-secret-token`

Token comparison uses constant-time digest comparison (`hmac.compare_digest`) to prevent timing attacks. Unauthorized requests receive an HTTP 401 response.

To disable the documentation UI entirely in production, set `docs=False` (the default).

---

## Understanding the UI Layout

The documentation UI organizes events into the following structure:

### Connection Controls

At the top of the page, a connection bar provides:

- A **Connect** button to establish a WebSocket connection to the server
- A status indicator showing connection state (disconnected, connecting, connected)
- The assigned connection ID and session metadata once connected

### Event Cards

Each registered event is displayed as an expandable card containing:

- **Event name** and **description** (from the `@socket.on()` decorator)
- **Direction badge** indicating the event type:
    - `LISTEN` -- events the server listens for (inbound)
    - `EMIT` -- events the handler sends back to the caller
    - `BROADCAST` -- events the handler broadcasts to a room
- **Tag grouping** -- events with the same `tags` value are grouped under collapsible sections
- **Deprecation indicator** -- events marked with `deprecated=True` are visually flagged
- **Payload schema table** -- field names, types, required/optional status, descriptions, and validation constraints, extracted directly from the Pydantic model

### Schema Extraction

Schemas are generated automatically from the Pydantic model in your handler signature:

```python
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    room_id: str = Field(description="Target chat room identifier")
    content: str = Field(description="Message body", max_length=500)

@socket.on("chat.send", tags=["messaging"], description="Send a message to a chat room.")
async def send(conn, payload: ChatMessage) -> None:
    ...
```

The documentation UI renders this as:

| Field | Type | Required | Description | Constraints |
|---|---|---|---|---|
| `room_id` | `string` | Yes | Target chat room identifier | |
| `content` | `string` | Yes | Message body | max length: 500 |

No manual schema files, no YAML, no annotations beyond standard Pydantic field definitions.

---

## Testing Events Interactively

The "Try it out" feature allows you to send WebSocket events directly from the documentation UI. This is the core testing workflow:

### Step 1: Connect

Click the **Connect** button. The status bar updates to show an active connection with your assigned connection ID.

### Step 2: Select an Event

Expand an event card by clicking on it. Click the **Try it out** button to activate the interactive editor.

### Step 3: Edit the Payload

The UI generates a pre-filled JSON template based on the Pydantic model:

```json
{
    "room_id": "",
    "content": ""
}
```

Edit the values as needed for your test case.

### Step 4: Send

Click **Send Event**. SocketSpec transmits the WebSocket frame to the server using the active connection.

### Step 5: Inspect the Response

The response panel displays all messages received from the server after sending the event:

- Direct replies from `conn.emit()` appear as event/payload pairs
- Broadcast messages from `rooms.broadcast()` appear if the connection is a member of the target room
- Validation errors appear as structured `__error__` envelopes with the specific field violations
- Handler errors appear as `HANDLER_ERROR` envelopes with the exception details

### Testing Multiple Clients

Open a second browser tab at the same `/socket-docs` URL and connect. Each tab gets an independent connection ID. This allows testing room broadcasts, multi-user flows, and pub/sub scenarios directly from the documentation UI.

---

## Real-Time Debug Inspector (`/socket-debug`)

When `debug=True` is set on `SocketApp`, a dedicated real-time debug inspector is mounted at `/socket-debug`.

The debug inspector provides:

- **Live event streaming** -- connection state transitions, room join/leave events, event routing decisions, and handler execution timing are streamed to the browser using Server-Sent Events (SSE)
- **Multi-client support** -- each browser tab receives its own independent event stream through per-client fan-out queues, so multiple developers can inspect the same server simultaneously without interfering with each other
- **Zero overhead when unused** -- when no clients are connected to the debug endpoint, no logging overhead is incurred

Navigate to `http://localhost:8000/socket-debug` to open the inspector. Events appear in real-time as connections interact with the server.

!!! note
    The debug inspector is intended for development only. Disable it in production by omitting `debug=True`.
