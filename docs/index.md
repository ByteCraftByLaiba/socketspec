# SocketSpec

**A type-safe, decorator-driven WebSocket framework for Python.**

Build production WebSocket APIs with the same patterns you already know from FastAPI -- decorators, Pydantic models, dependency injection, middleware -- and get interactive documentation for free.

---

## The Problem

WebSocket development in Python is fragmented. You write raw message loops, manually validate JSON payloads, build ad-hoc room management, and have no way for frontend teams to explore and test your events without writing custom client code. Every project reinvents the same plumbing.

## The Solution

SocketSpec provides a structured, opinionated framework that treats WebSocket events as first-class API endpoints:

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field
from socketspec import SocketApp, Connection
from socketspec.adapters.fastapi import mount

socket = SocketApp(docs=True)

class ChatMessage(BaseModel):
    room: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)

@socket.on("send_message", tags=["chat"], description="Send a message to a chat room.")
async def send_message(conn: Connection, payload: ChatMessage) -> None:
    await socket.rooms.broadcast(
        f"chat:{payload.room}",
        "new_message",
        {"from": conn.id, "text": payload.text},
    )

app = FastAPI()
mount(socket, app, path="/ws")
```

Start the server, open `/socket-docs`, and every registered event is browsable, testable, and documented -- no Swagger YAML, no manual schema writing.

---

## Key Capabilities

| Capability | Description |
|---|---|
| **Decorator-based event handlers** | `@socket.on("event")` with full type inference |
| **Pydantic payload validation** | Automatic schema extraction, constraint enforcement, structured error responses |
| **Interactive documentation UI** | `/socket-docs` -- Swagger-style event browser with live "Try it out" testing |
| **Room management** | Join, leave, broadcast with pattern-based guards and lifecycle hooks |
| **Authentication** | JWT and API key backends with pluggable `AuthBackend` protocol |
| **Rate limiting** | Token bucket algorithm, per-connection, configurable burst capacity |
| **Origin validation** | Wildcard and exact-match origin allowlists |
| **Session management** | Heartbeat ping/pong, idle timeout, max duration, token refresh warnings |
| **Middleware** | FIFO chain with the same `next_handler` pattern as ASGI middleware |
| **Dependency injection** | `Depends()` with support for generator-based cleanup via `AsyncExitStack` |
| **In-process TestClient** | Full-stack testing without a server, network, or ports |
| **Strict type safety** | Passes `mypy --strict` across the entire codebase |

---

## How It Compares

| Feature | python-socketio | Django Channels | SocketSpec |
|---|---|---|---|
| FastAPI-native mounting | No | No | Yes |
| Pydantic payload validation | No | No | Yes |
| Built-in interactive documentation | No | No | Yes |
| In-process TestClient | No | Partial | Yes |
| Room guards with pattern matching | Manual | Manual | Built-in |
| Dependency injection | No | No | Yes |
| Strict type checking | No | No | Yes |

---

## Quick Install

```bash
pip install socketspec[fastapi]
```

Requires Python 3.10 or later.

---

## Where to Go Next

<div class="grid cards" markdown>

-   **Installation**

    Set up SocketSpec in your project with the right extras for your framework.

    [:octicons-arrow-right-24: Installation Guide](getting-started/installation.md)

-   **Quickstart**

    Build and test a working WebSocket API in under five minutes.

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   **Interactive Documentation**

    Learn how to use the built-in `/socket-docs` UI to test events from your browser.

    [:octicons-arrow-right-24: Interactive Docs Guide](how-to/interactive-docs.md)

-   **Architecture**

    Understand the request lifecycle, component design, and extension points.

    [:octicons-arrow-right-24: Architecture Overview](concepts/architecture.md)

</div>
