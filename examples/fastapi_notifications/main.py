# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""FastAPI server-to-client notification broadcast example.

Demonstrates: subscribe/unsubscribe to topics, broadcast_all,
broadcast_except (all but sender), and direct emit to sender only.

Run:
    pip install socketspec[fastapi]
    uvicorn examples.fastapi_notifications.main:app --reload

Trigger notifications via HTTP:
    # Broadcast to all connected clients
    curl -X POST http://localhost:8000/notify/all \\
         -H "Content-Type: application/json" \\
         -d '{"title": "System Alert", "body": "Maintenance in 5 min"}'

    # Broadcast to a specific topic's subscribers
    curl -X POST http://localhost:8000/notify/alerts \\
         -H "Content-Type: application/json" \\
         -d '{"title": "Security", "body": "Please update your password"}'

Open:
    http://localhost:8000/socket-docs    -- connect and watch notifications
    http://localhost:8000/socket-debug   -- live event log
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

socket = SocketApp(docs=True, debug=True)

# ─── Payload / request models ─────────────────────────────────────────────────


class SubscribePayload(BaseModel):
    topic: str


class NotifyRequest(BaseModel):
    title: str
    body: str


# ─── WebSocket events ─────────────────────────────────────────────────────────


@socket.on(
    "subscribe",
    description="Subscribe to a named notification topic.",
    tags=["notifications"],
)
async def subscribe(conn: Connection, payload: SubscribePayload) -> None:
    """Add the connection to the topic room."""
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
    """Remove the connection from the topic room."""
    room = f"topic:{payload.topic}"
    await socket.rooms.leave(conn, room)
    await conn.emit("unsubscribed", {"topic": payload.topic})


@socket.on(
    "broadcast_all",
    description="Send a notification to every connected client (admin demo).",
    tags=["notifications"],
)
async def broadcast_all_event(conn: Connection, payload: NotifyRequest) -> None:
    """Broadcast a message to everyone in the global topic."""
    await socket.rooms.broadcast(
        "topic:global",
        "notification",
        {"title": payload.title, "body": payload.body, "topic": "global"},
    )
    await conn.emit("broadcast_sent", {"count": "all"})


@socket.on(
    "broadcast_except",
    description="Broadcast to all clients except the sender.",
    tags=["notifications"],
)
async def broadcast_except_event(conn: Connection, payload: NotifyRequest) -> None:
    """Broadcast to everyone in global topic, excluding the sender."""
    await socket.rooms.broadcast(
        "topic:global",
        "notification",
        {"title": payload.title, "body": payload.body, "topic": "global"},
        exclude={conn.id},
    )
    await conn.emit("broadcast_sent", {"count": "all_except_self"})


@socket.on(
    "direct_message",
    description="Send a notification only to the requesting client.",
    tags=["notifications"],
)
async def direct_message(conn: Connection, payload: NotifyRequest) -> None:
    """Emit a notification back exclusively to the sender."""
    await conn.emit("notification", {"title": payload.title, "body": payload.body, "topic": "direct"})


# ─── Lifecycle ────────────────────────────────────────────────────────────────


@socket.on_connect
async def on_connect(conn: Connection) -> None:
    """Auto-subscribe every connection to the global topic."""
    await socket.rooms.join(conn, "topic:global")
    await conn.emit("welcome", {"conn_id": conn.id})
    logger.info("Connection %s connected", conn.id)


# ─── FastAPI app + HTTP push endpoints ────────────────────────────────────────

app = FastAPI(
    title="SocketSpec Notifications Example",
    description="Server-push notifications via WebSocket.",
    version="0.1.1",
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
    """Push a notification to subscribers of a specific topic."""
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
