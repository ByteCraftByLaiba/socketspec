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

"""AI streaming example — LLM token streaming over WebSocket.

Demonstrates: streaming LLM tokens to a single client as they arrive,
using asyncio generators and per-connection state via dependency injection.

This example uses a mock token generator. Replace `mock_llm_stream()` with
an actual call to OpenAI, Anthropic, or any async LLM client.

Run:
    pip install socketspec[fastapi]
    uvicorn examples.ai_streaming.main:app --reload

Open:
    http://localhost:8000/socket-docs   — Try the "generate" event
    ws://localhost:8000/ws              — WebSocket endpoint

Protocol:
    Client → Server:   { "event": "generate", "payload": { "prompt": "..." } }
    Server → Client:   { "event": "token",    "payload": { "text": "...", "index": N } }  (repeated)
    Server → Client:   { "event": "done",     "payload": { "total_tokens": N } }
    Server → Client:   { "event": "error",    "payload": { "message": "..." } }
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

socket = SocketApp(docs=True)

# ─── Payload models ──────────────────────────────────────────────────────────


class GeneratePayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=4096)
    max_tokens: int = Field(default=200, ge=1, le=2048)


class TokenResponse(BaseModel):
    text: str
    index: int


class DoneResponse(BaseModel):
    total_tokens: int


# ─── Mock LLM stream ─────────────────────────────────────────────────────────


async def mock_llm_stream(prompt: str, max_tokens: int) -> AsyncIterator[str]:
    """Simulate an LLM streaming response token by token.

    Replace this with an actual async LLM client, e.g.:
        async for chunk in openai_client.chat.completions.create(stream=True, ...):
            yield chunk.choices[0].delta.content or ""
    """
    words = f"This is a simulated streaming response to: {prompt}".split()
    words = words[:max_tokens]
    for word in words:
        await asyncio.sleep(0.05)  # simulate network latency per token
        yield word + " "


# ─── Active stream tracking ───────────────────────────────────────────────────
# Maps conn_id → cancel_event so clients can interrupt a running stream.
_active_streams: dict[str, asyncio.Event] = {}


# ─── Event handlers ──────────────────────────────────────────────────────────


@socket.on(
    "generate",
    description="Start an LLM completion stream. Tokens arrive as 'token' events.",
    tags=["ai"],
    emits=[
        Emits("token",  model=TokenResponse,  description="One streamed token chunk"),
        Emits("done",   model=DoneResponse,   description="Stream complete"),
        Emits("error",  description="Stream error"),
    ],
)
async def generate(conn: Connection, payload: GeneratePayload) -> None:
    """Stream LLM tokens back to the requesting connection."""
    # Cancel any existing stream for this connection
    existing = _active_streams.get(conn.id)
    if existing:
        existing.set()

    cancel_event = asyncio.Event()
    _active_streams[conn.id] = cancel_event

    try:
        index = 0
        async for token_text in mock_llm_stream(payload.prompt, payload.max_tokens):
            if cancel_event.is_set():
                logger.info("Stream cancelled for connection %s", conn.id)
                break
            await conn.emit("token", {"text": token_text, "index": index})
            index += 1

        await conn.emit("done", {"total_tokens": index})
        logger.info(
            "Stream complete for connection %s — %d tokens", conn.id, index
        )

    except Exception as exc:
        logger.exception("Stream error for connection %s: %s", conn.id, exc)
        await conn.emit("error", {"message": str(exc)})

    finally:
        _active_streams.pop(conn.id, None)


@socket.on(
    "cancel",
    description="Cancel an in-progress LLM stream.",
    tags=["ai"],
)
async def cancel(conn: Connection) -> None:
    """Interrupt a running stream for this connection."""
    event = _active_streams.get(conn.id)
    if event:
        event.set()
        await conn.emit("cancelled", {"message": "Stream cancelled"})
    else:
        await conn.emit("cancelled", {"message": "No active stream"})


# ─── Lifecycle ────────────────────────────────────────────────────────────────


@socket.on_disconnect
async def on_disconnect(conn: Connection, reason: str) -> None:
    """Cancel any active stream when the client disconnects."""
    event = _active_streams.pop(conn.id, None)
    if event:
        event.set()
    logger.info("Connection %s disconnected: %s", conn.id, reason)


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="SocketSpec AI Streaming Example",
    description="Stream LLM tokens over WebSocket with cancellation support.",
    version="0.1.0",
)

mount(socket, app, path="/ws")
