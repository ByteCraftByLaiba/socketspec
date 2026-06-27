# How-to: Testing with TestClient

SocketSpec ships a `TestClient` that runs the full WebSocket stack in-process —
no server, no network, no ports. It is designed to work with `pytest-asyncio`.

---

## Setup

```bash
pip install socketspec[dev]
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## Basic Pattern

```python
import pytest
from socketspec import SocketApp
from socketspec.testing import TestClient
from pydantic import BaseModel

socket = SocketApp()

class Ping(BaseModel):
    seq: int

@socket.on("ping")
async def ping(conn, payload: Ping) -> None:
    await conn.emit("pong", {"seq": payload.seq})


@pytest.mark.asyncio
async def test_ping_pong():
    async with TestClient(socket) as client:
        conn = await client.connect()

        await conn.send("ping", {"seq": 42})

        response = await conn.receive()
        assert response["event"] == "pong"
        assert response["payload"]["seq"] == 42
```

---

## Testing Multiple Connections

```python
@pytest.mark.asyncio
async def test_two_clients():
    async with TestClient(socket) as client:
        alice = await client.connect()
        bob   = await client.connect()

        # Each connection has its own ID
        assert alice.id != bob.id

        await alice.send("join_room", {"room_id": "general"})
        await bob.send("join_room",   {"room_id": "general"})

        # Drain join confirmations
        await alice.receive()
        await bob.receive()

        await alice.send("send_message", {"room_id": "general", "text": "hello"})
        msg = await bob.receive()
        assert msg["event"] == "new_message"
```

---

## Testing Authentication

```python
from socketspec.security.auth import JWTAuth
import jwt

socket_with_auth = SocketApp(
    auth=JWTAuth(secret="test-secret", algorithm="HS256"),
)

@pytest.mark.asyncio
async def test_auth_required():
    async with TestClient(socket_with_auth) as client:
        # No token — should fail
        conn = await client.connect()
        # Connection should be None or closed on auth failure
        # (behaviour depends on your adapter; TestClient surfaces auth errors)

@pytest.mark.asyncio
async def test_auth_success():
    token = jwt.encode({"sub": "user_123"}, "test-secret", algorithm="HS256")
    async with TestClient(socket_with_auth) as client:
        conn = await client.connect(headers={"Authorization": f"Bearer {token}"})
        assert conn is not None
        assert conn.identity.user_id == "user_123"
```

---

## Testing Lifecycle Hooks

```python
joined_rooms = []

@socket.on_room_join
async def track_joins(conn, room: str) -> None:
    joined_rooms.append((conn.id, room))

@pytest.mark.asyncio
async def test_room_join_hook():
    async with TestClient(socket) as client:
        conn = await client.connect()
        await conn.send("join_room", {"room_id": "general"})
        await conn.receive()  # drain the join confirmation

        assert any(r[1] == "chat:general" for r in joined_rooms)
```

---

## Receive with Timeout

`receive()` has a default timeout of 5 seconds. Override it to speed up
tests that expect no response:

```python
import asyncio

@pytest.mark.asyncio
async def test_no_response_expected():
    async with TestClient(socket) as client:
        conn = await client.connect()
        await conn.send("fire_and_forget", {})

        with pytest.raises(asyncio.TimeoutError):
            await conn.receive(timeout=0.1)
```

---

## conftest.py Pattern

```python
# tests/conftest.py
import pytest
from socketspec.testing import TestClient
from myapp.main import socket  # your SocketApp instance

@pytest.fixture
async def client():
    async with TestClient(socket) as c:
        yield c

@pytest.fixture
async def conn(client):
    return await client.connect()
```

Then in tests:

```python
async def test_something(conn):
    await conn.send("my_event", {"key": "value"})
    response = await conn.receive()
    assert response["event"] == "expected_response"
```
