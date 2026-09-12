# Quickstart

Build a working WebSocket API, test it from your browser, and write your first automated test -- all in under five minutes.

---

## Step 1: Create the Application

Create a file called `main.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from socketspec import SocketApp, Connection
from socketspec.adapters.fastapi import mount

# Initialize SocketSpec with interactive docs enabled
socket = SocketApp(docs=True)


class Greeting(BaseModel):
    name: str


@socket.on("greet", description="Send a greeting and receive a personalized response.")
async def greet(conn: Connection, payload: Greeting) -> None:
    await conn.emit("hello", {"message": f"Hello, {payload.name}!"})


# Mount onto a FastAPI application
app = FastAPI()
mount(socket, app, path="/ws")
```

---

## Step 2: Start the Server

```bash
uvicorn main:app --reload
```

The server starts on `http://localhost:8000`. The WebSocket endpoint is available at `ws://localhost:8000/ws`.

---

## Step 3: Open the Interactive Documentation

Navigate to **http://localhost:8000/socket-docs** in your browser.

You will see the `greet` event listed with its payload schema. To test it:

1. Click **Connect** in the top bar. The status indicator changes to show an active connection.
2. Expand the **greet** event card.
3. Click **Try it out**.
4. The JSON editor is pre-filled with a template based on the Pydantic model. Enter a name:
   ```json
   {"name": "World"}
   ```
5. Click **Send Event**.
6. The server response appears inline: `{"event": "hello", "payload": {"message": "Hello, World!"}}`.

---

## Step 4: Connect from JavaScript

Any standard WebSocket client works. All messages use a simple JSON envelope:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
    ws.send(JSON.stringify({
        event: "greet",
        payload: { name: "World" }
    }));
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log(msg.event);   // "hello"
    console.log(msg.payload); // { message: "Hello, World!" }
};
```

---

## Step 5: Write an Automated Test

SocketSpec includes a `TestClient` that runs the full stack in-process -- no server, no network, no ports:

```python
import pytest
from socketspec.testing import TestClient
from main import socket

@pytest.mark.asyncio
async def test_greet():
    client = TestClient(socket)
    async with client.connect() as conn:
        await conn.emit("greet", {"name": "World"})
        response = await conn.receive("hello")
        assert response == {"message": "Hello, World!"}
```

Run it:

```bash
pytest test_main.py -v
```

---

## What Just Happened

In five lines of application code, SocketSpec provided:

- **Automatic payload validation** -- if the client omits `name` or sends an integer, they receive a structured `VALIDATION_ERROR` and the handler never executes.
- **Interactive documentation** -- the `/socket-docs` UI extracted the schema from the Pydantic model and rendered it as a testable event card.
- **In-process testing** -- `TestClient` exercises the full middleware, security, and routing stack without external infrastructure.

---

## Next Steps

- [Your First Event](../tutorial/first-event.md) -- understand the complete request lifecycle
- [Payload Validation](../tutorial/payload-validation.md) -- constraints, nested models, and error handling
- [Rooms and Broadcasting](../tutorial/rooms.md) -- pub/sub with pattern-based guards
- [Interactive Documentation Guide](../how-to/interactive-docs.md) -- the full guide to `/socket-docs`
