# Tutorial: Rooms

Rooms let you broadcast messages to groups of connections.
SocketSpec rooms support pattern-based names, guards, and lifecycle hooks.

---

## Creating a Room

Rooms are created lazily — they come into existence when the first connection
joins and are destroyed when the last connection leaves.

Register static rooms at startup if you want them to always exist:

```python
from socketspec import SocketApp
from socketspec.rooms import Room

socket = SocketApp(
    docs=True,
    rooms=[Room(name="lobby")],  # static room, always exists
)
```

---

## Joining a Room

```python
from pydantic import BaseModel

class JoinPayload(BaseModel):
    room_id: str

@socket.on("join_room", tags=["rooms"])
async def join_room(conn, payload: JoinPayload) -> None:
    room_name = f"chat:{payload.room_id}"
    await socket.rooms.join(conn, room_name)
    await conn.emit("joined", {"room": room_name})
```

After joining, `conn.rooms` contains the room name. Connections are
automatically removed from all their rooms on disconnect — no manual cleanup.

---

## Leaving a Room

```python
@socket.on("leave_room")
async def leave_room(conn, payload: JoinPayload) -> None:
    room_name = f"chat:{payload.room_id}"
    await socket.rooms.leave(conn, room_name)
    await conn.emit("left", {"room": room_name})
```

---

## Broadcasting to a Room

```python
class ChatMessage(BaseModel):
    room_id: str
    text: str

@socket.on("send_message")
async def send_message(conn, payload: ChatMessage) -> None:
    await socket.rooms.broadcast(
        f"chat:{payload.room_id}",
        "new_message",
        {"from": conn.id, "text": payload.text},
    )
```

All connections currently in `chat:{payload.room_id}` receive
`{"event": "new_message", "payload": {"from": "...", "text": "..."}}`.

---

## Room Guards (Permissions)

Use `@socket.room_guard("pattern")` to gate room access:

```python
@socket.room_guard("admin:{room_id}")
async def admin_only(conn, room_id: str) -> bool:
    return conn.identity.role == "admin"
```

The `{room_id}` variable in the pattern is extracted and passed as a keyword
argument to your guard function. The guard runs **before** the connection is
admitted to the room.

If the guard returns `False`, SocketSpec sends:

```json
{
  "event": "__error__",
  "payload": { "code": "PERMISSION_ERROR" }
}
```

### Multiple Guards

Register multiple patterns to protect multiple room namespaces:

```python
@socket.room_guard("chat:{room_id}")
async def chat_guard(conn, room_id: str) -> bool:
    return conn.identity.is_authenticated

@socket.room_guard("admin:{section}")
async def admin_guard(conn, section: str) -> bool:
    return conn.identity.role == "admin"
```

---

## Room Lifecycle Hooks

```python
@socket.on_room_join
async def on_join(conn, room: str) -> None:
    print(f"{conn.id} joined {room}")

@socket.on_room_leave
async def on_leave(conn, room: str) -> None:
    print(f"{conn.id} left {room}")
```

---

## Listing Room Members

```python
@socket.on("who_is_here")
async def who_is_here(conn, payload: JoinPayload) -> None:
    room_name = f"chat:{payload.room_id}"
    members = await socket.rooms.members(room_name)
    await conn.emit("members", {"room": room_name, "count": len(members)})
```

---

## Testing Rooms

```python
@pytest.mark.asyncio
async def test_broadcast():
    async with TestClient(socket) as client:
        alice = await client.connect()
        bob   = await client.connect()

        await alice.send("join_room", {"room_id": "general"})
        await bob.send("join_room",   {"room_id": "general"})

        # Drain join confirmations
        await alice.receive()
        await bob.receive()

        # Alice broadcasts
        await alice.send("send_message", {"room_id": "general", "text": "hi"})

        # Bob receives the broadcast
        msg = await bob.receive()
        assert msg["event"] == "new_message"
        assert msg["payload"]["text"] == "hi"
```
