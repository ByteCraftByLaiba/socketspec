# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""AI streaming example — LLM token streaming over WebSocket.

Demonstrates: streaming tokens to a single client using asyncio generators,
per-connection cancellation via conn.metadata, and debug mode.

Replace `mock_llm_stream()` with a real async LLM client:
    async for chunk in openai_client.chat.completions.create(stream=True, ...):
        yield chunk.choices[0].delta.content or ""

Run:
    pip install socketspec[fastapi]
    uvicorn examples.ai_streaming.main:app --reload

Open:
    http://localhost:8000/socket-docs    -- Try the "generate" event
    http://localhost:8000/socket-debug   -- Live event log

Protocol:
    Client -> Server:  {"event": "generate",  "payload": {"prompt": "..."}}
    Server -> Client:  {"event": "token",      "payload": {"text": "...", "index": N}} (repeated)
    Server -> Client:  {"event": "done",       "payload": {"total_tokens": N}}
    Client -> Server:  {"event": "cancel",     "payload": {}}
    Server -> Client:  {"event": "cancelled",  "payload": {"message": "..."}}
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from pydantic import BaseModel, Field

from socketspec import SocketApp
from socketspec.adapters.fastapi import mount
from socketspec.connection import Connection
from socketspec.registry import Emits

logger = logging.getLogger(__name__)

# ─── App setup ────────────────────────────────────────────────────────────────

socket = SocketApp(docs=True, debug=True)

# ─── Payload models ──────────────────────────────────────────────────────────


class GeneratePayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=4096, description="Prompt to complete")
    max_tokens: int = Field(default=200, ge=1, le=2048, description="Maximum tokens to generate")


class TokenResponse(BaseModel):
    text: str
    index: int


class DoneResponse(BaseModel):
    total_tokens: int


# ─── Mock LLM stream ─────────────────────────────────────────────────────────


async def mock_llm_stream(prompt: str, max_tokens: int) -> AsyncIterator[str]:
    """Simulate an LLM streaming token by token.

    Replace this body with an actual async LLM client call.
    """
    words = f"This is a simulated streaming response to: {prompt}".split()
    words = words[:max_tokens]
    for word in words:
        await asyncio.sleep(0.05)
        yield word + " "


# ─── Event handlers ──────────────────────────────────────────────────────────


@socket.on(
    "generate",
    description="Start an LLM completion stream. Tokens arrive as 'token' events.",
    tags=["ai"],
    emits=[
        Emits("token",     model=TokenResponse, description="One streamed token chunk"),
        Emits("done",      model=DoneResponse,  description="Stream complete"),
        Emits("cancelled",                      description="Stream was cancelled"),
        Emits("error",                          description="Stream error"),
    ],
)
async def generate(conn: Connection, payload: GeneratePayload) -> None:
    """Stream LLM tokens back to the requesting connection.

    Cancellation is stored per-connection in conn.metadata so there is no
    module-level mutable state. A new generate call cancels any previous
    in-progress stream for the same connection.
    """
    # Cancel any existing stream for this connection
    existing: asyncio.Event | None = conn.metadata.get("cancel_event")
    if existing is not None:
        existing.set()

    cancel_event = asyncio.Event()
    conn.metadata["cancel_event"] = cancel_event

    try:
        index = 0
        async for token_text in mock_llm_stream(payload.prompt, payload.max_tokens):
            if cancel_event.is_set():
                logger.info("Stream cancelled for connection %s", conn.id)
                await conn.emit("cancelled", {"message": "Stream cancelled by client"})
                return

            await conn.emit("token", {"text": token_text, "index": index})
            index += 1

        await conn.emit("done", {"total_tokens": index})
        logger.info("Stream complete for connection %s — %d tokens", conn.id, index)

    except Exception as exc:
        logger.exception("Stream error for connection %s: %s", conn.id, exc)
        await conn.emit("error", {"message": str(exc)})

    finally:
        conn.metadata.pop("cancel_event", None)


@socket.on(
    "cancel",
    description="Cancel an in-progress LLM stream.",
    tags=["ai"],
    emits=[Emits("cancelled", description="Confirmation that the stream was stopped")],
)
async def cancel(conn: Connection) -> None:
    """Interrupt the running stream for this connection."""
    event: asyncio.Event | None = conn.metadata.get("cancel_event")
    if event is not None:
        event.set()
        await conn.emit("cancelled", {"message": "Stream cancelled"})
    else:
        await conn.emit("cancelled", {"message": "No active stream to cancel"})


# ─── Lifecycle ────────────────────────────────────────────────────────────────


@socket.on_disconnect
async def on_disconnect(conn: Connection, reason: str) -> None:
    """Cancel any active stream when the client disconnects."""
    event: asyncio.Event | None = conn.metadata.pop("cancel_event", None)
    if event is not None:
        event.set()
    logger.info("Connection %s disconnected: %s", conn.id, reason)


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="SocketSpec AI Streaming Example",
    description="Stream LLM tokens over WebSocket with per-connection cancellation.",
    version="0.1.1",
)

mount(socket, app, path="/ws")
