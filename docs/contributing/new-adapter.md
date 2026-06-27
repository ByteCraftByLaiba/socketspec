# Writing a New Adapter

This guide walks through implementing a SocketSpec adapter for a new web framework.
An adapter bridges the framework's WebSocket object to SocketSpec's `RawSocket` protocol.

---

## What an Adapter Does

SocketSpec is framework-agnostic. It defines a `RawSocket` protocol:

```python
class RawSocket(Protocol):
    async def receive_text(self) -> str: ...
    async def send_json(self, data: dict) -> None: ...
    async def close(self, code: int = 1000) -> None: ...
```

An adapter:

1. Wraps the framework's WebSocket object in a class that implements `RawSocket`
2. Calls `socket_app.handle_connect()` at the start of the connection
3. Loops on `socket_app.handle_event()` for each inbound message
4. Calls `socket_app.handle_disconnect()` when the connection closes

---

## Step 1 — Implement `RawSocket`

Study the FastAPI adapter as a reference:
[`src/socketspec/adapters/fastapi.py`](../../src/socketspec/adapters/fastapi.py)

For a hypothetical Litestar adapter:

```python
# src/socketspec/adapters/litestar.py

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from socketspec.connection import RawSocket

if TYPE_CHECKING:
    from litestar.connection import WebSocket

logger = logging.getLogger(__name__)


class LitestarSocketWrapper:
    """Wraps a Litestar WebSocket to implement the RawSocket protocol."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def receive_text(self) -> str:
        return await self._ws.receive_data(mode="text")

    async def send_json(self, data: dict[str, Any]) -> None:
        await self._ws.send_json(data)

    async def close(self, code: int = 1000) -> None:
        await self._ws.close(code=code)
```

---

## Step 2 — Implement the Mount Function

```python
def mount(socket_app: SocketApp, router: Router, path: str = "/ws") -> None:
    """Register a SocketSpec WebSocket handler on a Litestar Router."""

    @websocket(path=path)
    async def ws_handler(socket: WebSocket) -> None:
        await socket.accept()

        headers     = dict(socket.headers)
        query_params = dict(socket.query_params)
        raw          = LitestarSocketWrapper(socket)

        conn = await socket_app.handle_connect(raw, headers, query_params)
        if conn is None:
            return  # rejected at the security layer

        try:
            while True:
                try:
                    data = await socket.receive_data(mode="text")
                except Exception:
                    break
                await socket_app.handle_event(conn, data)
        finally:
            await socket_app.handle_disconnect(conn, "client_close")

    router.register(ws_handler)
```

---

## Step 3 — Lazy Imports

Do **not** import the framework at module level — import inside the `mount()`
function body. This keeps `socketspec.adapters.litestar` importable without
Litestar installed.

```python
def mount(socket_app: SocketApp, router: Router, path: str = "/ws") -> None:
    from litestar import websocket  # noqa: PLC0415 — lazy import
    ...
```

---

## Step 4 — Tests

Create `tests/adapters/test_litestar_adapter.py`:

```python
import pytest
from socketspec import SocketApp
from socketspec.testing import TestClient

# Test that the adapter correctly passes headers to handle_connect
@pytest.mark.asyncio
async def test_adapter_passes_headers():
    socket = SocketApp()

    received_headers = {}

    @socket.on_connect
    async def on_connect(conn):
        received_headers.update(conn.headers)

    async with TestClient(socket) as client:
        await client.connect(headers={"x-user-id": "abc"})

    assert received_headers.get("x-user-id") == "abc"
```

---

## Step 5 — Register the Adapter

1. Add the adapter file to `src/socketspec/adapters/`
2. Add `__init__.py` if needed
3. Add the framework as an optional dependency in `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   litestar = ["litestar>=2.0"]
   ```
4. Add the framework to the `all` extra
5. Update `docs/how-to/` with a guide for the new adapter

---

## Invariants to Preserve

Your adapter must never:

- Call `handle_event()` before `handle_connect()` returns a non-None `conn`
- Catch exceptions from `handle_event()` silently (handler errors are already caught internally)
- Call `handle_disconnect()` more than once per connection
- Store connection state outside of `ConnectionManager` (INV-1)

See [`.context/SYSTEM_CURRENT.md`](../../.context/SYSTEM_CURRENT.md) for the full
list of system invariants.
