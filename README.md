# SocketSpec

**FastAPI-style WebSocket framework with built-in interactive docs and testing.**

[![CI](https://github.com/ByteCraftByLaiba/socketspec/actions/workflows/ci.yml/badge.svg)](https://github.com/ByteCraftByLaiba/socketspec/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/socketspec)](https://pypi.org/project/socketspec/)
[![Python](https://img.shields.io/pypi/pyversions/socketspec)](https://pypi.org/project/socketspec/)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen)](https://github.com/ByteCraftByLaiba/socketspec)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Install

```bash
pip install socketspec[fastapi]
```

---

## Quickstart

```python
from fastapi import FastAPI
from pydantic import BaseModel
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount

socket = SocketApp(docs=True)

class ChatMessage(BaseModel):
    room: str
    text: str

class MessageAck(BaseModel):
    status: str
    message_id: str

@socket.on(
    "send_message",
    description="Send a chat message to a room.",
    tags=["chat"],
    emits=[Emits("message_ack", model=MessageAck, description="Delivery confirmation")],
    broadcasts=[Broadcasts("new_message", room="chat:{room}", description="Delivered to room members")],
)
async def send_message(conn, payload: ChatMessage) -> None:
    await conn.emit("message_ack", {"status": "ok", "message_id": "abc123"})
    await socket.rooms.broadcast(
        "chat:" + payload.room,
        "new_message",
        {"from": conn.id, "text": payload.text},
    )

app = FastAPI()
mount(socket, app, path="/ws")
```

```bash
uvicorn main:app --reload
```

---

## Docs UI

Open **`/socket-docs`** in your browser after starting the server.

<!-- screenshot: add after first live demo -->

- Click an event card to expand its schema
- Hit **Try it out** to send a live WebSocket message
- See the server response appear inline, without leaving the browser
- Open a second tab and connect as a different user to test broadcasts

---

## Why SocketSpec

| Feature | python-socketio | channels (Django) | SocketSpec |
|---|---|---|---|
| FastAPI-native | ✗ | ✗ | ✅ |
| Pydantic payload validation | ✗ | ✗ | ✅ |
| Built-in interactive docs | ✗ | ✗ | ✅ |
| `TestClient` for unit tests | ✗ | partial | ✅ |
| Room guards / permissions | manual | manual | ✅ |
| Dependency injection (`Depends`) | ✗ | ✗ | ✅ |
| Type-safe (`mypy --strict`) | ✗ | ✗ | ✅ |

---

## Core Concepts

**Event handlers** look exactly like FastAPI route handlers:

```python
@socket.on("join_room", tags=["rooms"])
async def join_room(conn: Connection, payload: JoinPayload) -> None:
    await socket.rooms.join(conn, f"chat:{payload.room_id}")
```

**Rooms** with pattern-based guards:

```python
@socket.room_guard("admin:{room}")
async def admin_only(conn: Connection, room: str) -> bool:
    return conn.identity.role == "admin"
```

**Testing** without a real server:

```python
from socketspec.testing import TestClient

async def test_send_message():
    async with TestClient(socket) as client:
        conn = await client.connect()
        await conn.send("send_message", {"room": "general", "text": "hello"})
        response = await conn.receive()
        assert response["event"] == "message_ack"
```

---

## Links

- [Documentation](https://socketspec.dev)
- [GitHub](https://github.com/ByteCraftByLaiba/socketspec)
- [PyPI](https://pypi.org/project/socketspec/)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
Created and maintained by [Laiba Shahab](https://github.com/ByteCraftByLaiba).
