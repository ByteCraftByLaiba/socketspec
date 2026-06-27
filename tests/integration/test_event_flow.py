# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import anyio
from pydantic import BaseModel

from socketspec.app import SocketApp
from socketspec.registry import Emits
from socketspec.testing import TestClient


class EchoPayload(BaseModel):
    text: str


class StrictPayload(BaseModel):
    required_field: str


async def test_full_event_flow_echoes_payload() -> None:
    app = SocketApp()

    @app.on("echo", emits=[Emits("echoed", model=EchoPayload)])
    async def handle_echo(conn: object, payload: EchoPayload) -> None:
        await conn.emit("echoed", payload.model_dump())

    async with TestClient(app).connect() as conn:
        await conn.emit("echo", {"text": "hello"})
        await anyio.sleep(0.05)
        response = await conn.receive("echoed")
        assert response["text"] == "hello"


async def test_unknown_event_returns_unknown_event_error() -> None:
    app = SocketApp()
    async with TestClient(app).connect() as conn:
        await conn.emit("nonexistent", {})
        await anyio.sleep(0.05)
        error = await conn.receive("__error__")
        assert error["code"] == "UNKNOWN_EVENT"


async def test_validation_error_for_invalid_payload() -> None:
    app = SocketApp()

    @app.on("strict")
    async def handle_strict(conn: object, payload: StrictPayload) -> None:
        pass

    async with TestClient(app).connect() as conn:
        await conn.emit("strict", {})
        await anyio.sleep(0.05)
        error = await conn.receive("__error__")
        assert error["code"] == "VALIDATION_ERROR"
