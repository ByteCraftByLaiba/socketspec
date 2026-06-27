# Quickstart

Get a working WebSocket API running in under 5 minutes.

---

## 1. Install

```bash
pip install socketspec[fastapi]
```

---

## 2. Create `main.py`

```python
from fastapi import FastAPI
from pydantic import BaseModel
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount

# Create the WebSocket application
socket = SocketApp(docs=True)

# Define a payload model
class Greet(BaseModel):
    name: str

# Register an event handler
@socket.on("greet", description="Say hello to the server.")
async def greet(conn, payload: Greet) -> None:
    await conn.emit("hello", {"message": f"Hello, {payload.name}!"})

# Mount onto FastAPI
app = FastAPI()
mount(socket, app, path="/ws")
```

---

## 3. Run

```bash
uvicorn main:app --reload
```

---

## 4. Open the Docs UI

Navigate to **http://localhost:8000/socket-docs**

You will see the `greet` event card. Click it to expand, then:

1. Click **Try it out**
2. The editor pre-fills with `{"name": ""}`
3. Change it to `{"name": "Laiba"}`
4. Click **▶ Send Event**
5. The server responds with `{"event": "hello", "payload": {"message": "Hello, Laiba!"}}`
   — rendered inline below the editor

---

## 5. Test It Programmatically

```python
import pytest
from socketspec.testing import TestClient

@pytest.mark.asyncio
async def test_greet():
    async with TestClient(socket) as client:
        conn = await client.connect()
        await conn.send("greet", {"name": "Laiba"})
        msg = await conn.receive()
        assert msg["event"] == "hello"
        assert msg["payload"]["message"] == "Hello, Laiba!"
```

```bash
pytest test_main.py -v
```

---

## What's Next?

- [First Event Tutorial](tutorial/first-event.md) — understand the full request lifecycle
- [Payload Validation](tutorial/payload-validation.md) — Pydantic models and error handling
- [Rooms](tutorial/rooms.md) — pub/sub with room guards
