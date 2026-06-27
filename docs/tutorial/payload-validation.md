# Tutorial: Payload Validation

SocketSpec uses Pydantic v2 to validate every incoming event payload.
This tutorial covers the full validation system — constraints, nested models,
error responses, and custom validators.

---

## Basic Validation

Define a Pydantic model and use it as the second parameter to your handler:

```python
from pydantic import BaseModel, Field

class SendMessage(BaseModel):
    room: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)

@socket.on("send_message")
async def send_message(conn, payload: SendMessage) -> None:
    # payload.room and payload.text are guaranteed valid here
    await socket.rooms.broadcast(f"chat:{payload.room}", "new_message", {
        "text": payload.text,
    })
```

If the client sends `{"room": "", "text": "hi"}`, SocketSpec sends back:

```json
{
  "event": "__error__",
  "payload": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid message format",
    "request_id": "a3f9...",
    "details": {}
  }
}
```

The handler is **never called** on validation failure.

---

## Optional Fields and Defaults

```python
from typing import Literal

class JoinRoom(BaseModel):
    room_id: str
    role: Literal["member", "moderator"] = "member"
    mute: bool = False

@socket.on("join_room")
async def join_room(conn, payload: JoinRoom) -> None:
    # payload.role defaults to "member" if not provided
    await socket.rooms.join(conn, f"room:{payload.room_id}")
```

---

## Nested Models

```python
from pydantic import BaseModel

class Recipient(BaseModel):
    user_id: str
    notify: bool = True

class DirectMessage(BaseModel):
    to: Recipient
    text: str

@socket.on("direct_message")
async def direct_message(conn, payload: DirectMessage) -> None:
    if payload.to.notify:
        # send push notification
        pass
```

---

## Custom Validators

```python
from pydantic import BaseModel, field_validator

class BidPayload(BaseModel):
    item_id: str
    amount: float

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Bid amount must be positive")
        return v
```

If `amount` is `0` or negative, SocketSpec catches the `ValidationError` and
sends back `VALIDATION_ERROR` — same as any other Pydantic failure.

---

## Events Without a Payload

If your handler takes no payload argument, any payload sent by the client is
silently ignored:

```python
@socket.on("ping")
async def ping(conn) -> None:
    await conn.emit("pong", {})
```

---

## Payload Size Limit

By default, SocketSpec rejects payloads larger than **64 KB**:

```json
{ "event": "__error__", "payload": { "code": "PAYLOAD_TOO_LARGE" } }
```

Increase or decrease the limit when creating `SocketApp`:

```python
socket = SocketApp(max_payload_size=1_048_576)  # 1 MB
```

---

## How Validation Fits in the Pipeline

```
JSON parse  ──▶ VALIDATION_ERROR (malformed JSON or missing "event" key)
    │
    ▼
Pydantic    ──▶ VALIDATION_ERROR (field constraint violation)
    │
    ▼
Handler runs
```

---

## Next

- [Rooms](rooms.md) — broadcasting to groups of connections
