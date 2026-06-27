# Copyright (c) 2025 Laiba Shahab. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""FastAPI chat room example.

Demonstrates: rooms, room guards, broadcasts, and lifecycle hooks.

Run:
    pip install socketspec[fastapi]
    uvicorn examples.fastapi_chat.main:app --reload

Open:
    http://localhost:8000/socket-docs   — interactive docs UI
    ws://localhost:8000/ws              — WebSocket endpoint
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
    rooms=[Room(name="lobby")],  # "lobby" always exists
)

# ─── Payload models ──────────────────────────────────────────────────────────


class JoinPayload(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)


class MessagePayload(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)


class LeavePayload(BaseModel):
    room_id: str = Field(min_length=1, max_length=64)


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
    # In production, check conn.identity.user_id is not banned, etc.
    _ = room_id
    return True


# ─── Event handlers ───────────────────────────────────────────────────────────


@socket.on(
    "join_room",
    description="Join a chat room and start receiving messages.",
    tags=["chat"],
    emits=[Emits("join_ack", model=JoinAck, description="Confirms room membership")],
    broadcasts=[
        Broadcasts(
            "member_update",
            room="chat:{room_id}",
            model=MemberUpdate,
            description="Notifies existing members of a new arrival",
        )
    ],
)
async def join_room(conn: Connection, payload: JoinPayload) -> None:
    """Join a chat room."""
    room_name = f"chat:{payload.room_id}"
    await socket.rooms.join(conn, room_name)

    members = await socket.rooms.members(room_name)
    count = len(members)

    # Confirm to the joining connection
    await conn.emit("join_ack", {"room": room_name, "member_count": count})

    # Notify everyone else in the room
    await socket.rooms.broadcast(
        room_name,
        "member_update",
        {
            "room": room_name,
            "event": "joined",
            "conn_id": conn.id,
            "member_count": count,
        },
        exclude={conn.id},
    )
    logger.info("Connection %s joined %s (%d members)", conn.id, room_name, count)


@socket.on(
    "send_message",
    description="Send a message to a chat room.",
    tags=["chat"],
    broadcasts=[
        Broadcasts(
            "new_message",
            room="chat:{room_id}",
            model=NewMessage,
            description="Delivered to all members of the room",
        )
    ],
)
async def send_message(conn: Connection, payload: MessagePayload) -> None:
    """Broadcast a chat message to the room."""
    room_name = f"chat:{payload.room_id}"

    if room_name not in conn.rooms:
        await conn.emit(
            "__error__",
            {"code": "PERMISSION_ERROR", "message": "Join the room first"},
        )
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
    """Leave a chat room."""
    room_name = f"chat:{payload.room_id}"
    await socket.rooms.leave(conn, room_name)

    members = await socket.rooms.members(room_name)
    count = len(members)

    await socket.rooms.broadcast(
        room_name,
        "member_update",
        {
            "room": room_name,
            "event": "left",
            "conn_id": conn.id,
            "member_count": count,
        },
    )
    await conn.emit("leave_ack", {"room": room_name})


# ─── Lifecycle hooks ──────────────────────────────────────────────────────────


@socket.on_connect
async def on_connect(conn: Connection) -> None:
    """Welcome new connections and add them to the lobby."""
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
    version="0.1.0",
)

mount(socket, app, path="/ws")
