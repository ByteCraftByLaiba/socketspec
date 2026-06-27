# SocketSpec

**FastAPI-style WebSocket framework with built-in interactive docs and testing.**

---

## What is SocketSpec?

SocketSpec lets you build production WebSocket APIs the same way you build FastAPI
HTTP APIs — with decorators, Pydantic models, dependency injection, and automatic
interactive documentation.

```python
from fastapi import FastAPI
from pydantic import BaseModel
from socketspec import SocketApp
from socketspec.adapters.fastapi import mount

socket = SocketApp(docs=True)

class ChatMessage(BaseModel):
    room: str
    text: str

@socket.on("send_message", tags=["chat"])
async def send_message(conn, payload: ChatMessage) -> None:
    await socket.rooms.broadcast(f"chat:{payload.room}", "new_message", {
        "from": conn.id,
        "text": payload.text,
    })

app = FastAPI()
mount(socket, app, path="/ws")
```

Open `/socket-docs` and you immediately get an interactive event browser — no
Swagger YAML, no manual schema writing.

---

## Features at a Glance

| Feature | Notes |
|---|---|
| Decorator-based event handlers | `@socket.on("event_name")` |
| Pydantic payload validation | Second parameter to handler is the model |
| Room management | Pattern matching with guards |
| Heartbeat / ping-pong | Automatic ghost-connection detection |
| Rate limiting | Token bucket per connection |
| JWT + API key auth | Pluggable `AuthBackend` protocol |
| Origin validation | Wildcard and exact-match |
| Middleware | FIFO chain, same API as FastAPI |
| Dependency injection | `Depends()` with yield-based cleanup |
| Interactive docs UI | `/socket-docs` — Swagger-style event browser |
| TestClient | In-process testing without a server |
| `mypy --strict` | Full type safety |

---

## Install

```bash
pip install socketspec[fastapi]
```

---

## Next Steps

- [Quickstart](quickstart.md) — Running in 5 minutes
- [First Event Tutorial](tutorial/first-event.md) — Step-by-step walkthrough
- [API Reference: SocketApp](reference/socketapp.md) — Full parameter reference
