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

"""FastAPI server-to-client notification broadcast example.

Demonstrates: pushing notifications from an HTTP endpoint to all connected
WebSocket clients or a specific user, without the client sending an event first.

Run:
    pip install socketspec[fastapi]
    uvicorn examples.fastapi_notifications.main:app --reload

Trigger a broadcast:
    curl -X POST http://localhost:8000/notify/all \
         -H "Content-Type: application/json" \
         -d '{"title": "Maintenance", "body": "Server restart in 5 minutes"}'

Open:
    http://localhost:8000/socket-docs   — connect and watch notifications arrive
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from socketspec import SocketApp
from socketspec.adapters.fastapi import mount
from socketspec.connection import Connection

logger = logging.getLogger(__name__)

# ─── App setup ────────────────────────────────────────────────────────────────

socket = SocketApp(docs=True)

# ─── Payload / request models ─────────────────────────────────────────────────


class SubscribePayload(BaseModel):
    topic: str  # e.g. "alerts", "news", "orders"


class NotifyRequest(BaseModel):
    title: str
    body: str


# ─── WebSocket events ─────────────────────────────────────────────────────────


@socket.on(
    "subscribe",
    description="Subscribe to a notification topic.",
    tags=["notifications"],
)
async def subscribe(conn: Connection, payload: SubscribePayload) -> None:
    """Add the connection to a topic room."""
    room = f"topic:{payload.topic}"
    await socket.rooms.join(conn, room)
    await conn.emit("subscribed", {"topic": payload.topic})
    logger.info("Connection %s subscribed to %s", conn.id, payload.topic)


@socket.on(
    "unsubscribe",
    description="Unsubscribe from a notification topic.",
    tags=["notifications"],
)
async def unsubscribe(conn: Connection, payload: SubscribePayload) -> None:
    """Remove the connection from a topic room."""
    room = f"topic:{payload.topic}"
    await socket.rooms.leave(conn, room)
    await conn.emit("unsubscribed", {"topic": payload.topic})


# ─── Lifecycle ────────────────────────────────────────────────────────────────


@socket.on_connect
async def on_connect(conn: Connection) -> None:
    """Auto-subscribe every connection to the "global" topic."""
    await socket.rooms.join(conn, "topic:global")
    await conn.emit("welcome", {"conn_id": conn.id})
    logger.info("Connection %s connected", conn.id)


# ─── FastAPI HTTP endpoints to push notifications ─────────────────────────────

app = FastAPI(
    title="SocketSpec Notifications Example",
    description="Server-push notifications via WebSocket.",
    version="0.1.0",
)

mount(socket, app, path="/ws")


@app.post("/notify/all", summary="Broadcast to all connected clients")
async def notify_all(request: NotifyRequest) -> dict[str, str]:
    """Push a notification to every connected WebSocket client."""
    await socket.rooms.broadcast(
        "topic:global",
        "notification",
        {"title": request.title, "body": request.body, "topic": "global"},
    )
    return {"status": "sent", "topic": "global"}


@app.post("/notify/{topic}", summary="Broadcast to subscribers of a topic")
async def notify_topic(topic: str, request: NotifyRequest) -> dict[str, str]:
    """Push a notification to all subscribers of a specific topic."""
    room = f"topic:{topic}"
    try:
        await socket.rooms.broadcast(
            room,
            "notification",
            {"title": request.title, "body": request.body, "topic": topic},
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Topic '{topic}' not found or empty") from exc

    return {"status": "sent", "topic": topic}


@app.get("/connections", summary="Count active WebSocket connections")
async def list_connections() -> dict[str, int]:
    """Return the number of currently active connections."""
    members = await socket.rooms.members("topic:global")
    return {"active_connections": len(members)}
