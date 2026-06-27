# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""FastAPI chat room example.

Demonstrates: rooms, room guards, broadcasts, and lifecycle hooks.

Run:
    pip install socketspec[fastapi]
    uvicorn examples.fastapi_chat.main:app --reload

Open:
    http://localhost:8000/socket-docs    -- interactive docs UI
    http://localhost:8000/socket-debug   -- live event log
    ws://localhost:8000/ws              -- WebSocket endpoint

Manual test sequence for a frontend developer:
    1. Connect two browser tabs to ws://localhost:8000/ws
    2. In Tab 1: {"event": "join_room", "payload": {"room_id": "general"}}
    3. In Tab 2: {"event": "join_room", "payload": {"room_id": "general"}}
       -> Both tabs receive member_update with member_count: 2
    4. In Tab 1: {"event": "send_message", "payload": {"room_id": "general", "text": "hello"}}
       -> Tab 2 receives new_message event
    5. In Tab 1: {"event": "leave_room", "payload": {"room_id": "general"}}
       -> Tab 2 receives member_update with event: "left"
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel, Field

from socketspec import SocketApp
from socketspec.adapters.fastapi import mount
from socketspec.connection import Connection
from socketspec.registry import Broadcasts, Emits
from socketspec.rooms import Room

logger = logging.getLogger(__name__)

# ─── App setup ────────────────────────────────────────────────────────────────

socket = SocketApp(
    docs=True,
    debug=True,
    rooms=[Room(name="lobby")],
)

# ─── Payload models ──────────────────────────────────────────────────────────


class JoinPayload(BaseModel):
    room_id: str = Field(min_length=1, max_length=64, description="Room identifier to join")


class MessagePayload(BaseModel):
    room_id: str = Field(min_length=1, max_length=64, description="Target room identifier")
    text: str = Field(min_length=1, max_length=500, description="Message text to broadcast")


class LeavePayload(BaseModel):
    room_id: str = Field(min_length=1, max_length=64, description="Room identifier to leave")


# ─── Response models ─────────────────────────────────────────────────────────


class JoinAck(BaseModel):
    room: str
    member_count: int


class NewMessage(BaseModel):
    from_conn: str
    text: str
    room: str


class MemberUpdate(BaseModel):
    room: str
    event: str  # "joined" | "left"
    conn_id: str
    member_count: int


# ─── Room guard ───────────────────────────────────────────────────────────────


@socket.room_guard("chat:{room_id}")
async def chat_room_guard(conn: Connection, room_id: str) -> bool:
    """Allow any connected user into any chat room."""
    _ = room_id
    return True


# ─── Event handlers ───────────────────────────────────────────────────────────


@socket.on(
    "join_room",
    description="Join a named chat room and start receiving messages.",
    tags=["chat"],
    emits=[Emits("join_ack", model=JoinAck, description="Confirms room membership")],
    broadcasts=[
        Broadcasts(
            "member_update",
            room="chat:{room_id}",
            model=MemberUpdate,
            description="Notifies existing members of the new arrival",
        )
    ],
)
async def join_room(conn: Connection, payload: JoinPayload) -> None:
    """Put the client into a named room and notify all members."""
    room_name = f"chat:{payload.room_id}"
    await socket.rooms.join(conn, room_name)

    members = await socket.rooms.members(room_name)
    count = len(members)

    # Confirm membership to the joining client
    await conn.emit("join_ack", {"room": room_name, "member_count": count})

    # Notify everyone else already in the room
    await socket.rooms.broadcast(
        room_name,
        "member_update",
        {"room": room_name, "event": "joined", "conn_id": conn.id, "member_count": count},
        exclude={conn.id},
    )
    logger.info("Connection %s joined %s (%d members)", conn.id, room_name, count)


@socket.on(
    "send_message",
    description="Send a text message to everyone in a room.",
    tags=["chat"],
    broadcasts=[
        Broadcasts(
            "new_message",
            room="chat:{room_id}",
            model=NewMessage,
            description="Delivered to all room members including sender",
        )
    ],
)
async def send_message(conn: Connection, payload: MessagePayload) -> None:
    """Broadcast a message to all connections in the target room."""
    room_name = f"chat:{payload.room_id}"

    if room_name not in conn.rooms:
        await conn.emit("__error__", {"code": "PERMISSION_ERROR", "message": "Join the room first"})
        return

    await socket.rooms.broadcast(
        room_name,
        "new_message",
        {"from_conn": conn.id, "text": payload.text, "room": room_name},
    )


@socket.on(
    "leave_room",
    description="Leave a chat room.",
    tags=["chat"],
    broadcasts=[
        Broadcasts(
            "member_update",
            room="chat:{room_id}",
            model=MemberUpdate,
            description="Notifies remaining members",
        )
    ],
)
async def leave_room(conn: Connection, payload: LeavePayload) -> None:
    """Remove the client from the room and notify remaining members."""
    room_name = f"chat:{payload.room_id}"
    await socket.rooms.leave(conn, room_name)

    members = await socket.rooms.members(room_name)
    count = len(members)

    await socket.rooms.broadcast(
        room_name,
        "member_update",
        {"room": room_name, "event": "left", "conn_id": conn.id, "member_count": count},
    )
    await conn.emit("leave_ack", {"room": room_name})


# ─── Lifecycle hooks ──────────────────────────────────────────────────────────


@socket.on_connect
async def on_connect(conn: Connection) -> None:
    """Welcome new connections and add them to the global lobby."""
    await socket.rooms.join(conn, "lobby")
    await conn.emit("welcome", {"conn_id": conn.id, "message": "Connected to chat server"})
    logger.info("New connection: %s", conn.id)


@socket.on_disconnect
async def on_disconnect(conn: Connection, reason: str) -> None:
    logger.info("Disconnected: %s (%s)", conn.id, reason)


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="SocketSpec Chat Example",
    description="Real-time chat rooms built with SocketSpec.",
    version="0.1.1",
)

mount(socket, app, path="/ws")
