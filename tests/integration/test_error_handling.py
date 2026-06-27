# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import anyio

from socketspec.app import SocketApp
from socketspec.security.ratelimit import RateLimit
from socketspec.testing import TestClient


async def test_handler_error_emits_handler_error_code() -> None:
    app = SocketApp()

    @app.on("boom")
    async def handle_boom(conn: object, payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    async with TestClient(app).connect() as conn:
        await conn.emit("boom", {})
        await anyio.sleep(0.05)
        error = await conn.receive("__error__")
        assert error["code"] == "HANDLER_ERROR"


async def test_rate_limit_error_when_limit_exceeded() -> None:
    app = SocketApp(rate_limit=RateLimit(events=1, per_seconds=60))

    @app.on("tick")
    async def handle_tick(conn: object, payload: dict[str, object]) -> None:
        await conn.emit("tick_ok", {})

    async with TestClient(app).connect() as conn:
        await conn.emit("tick", {})
        await anyio.sleep(0.05)
        await conn.receive("tick_ok")
        await conn.emit("tick", {})
        await anyio.sleep(0.05)
        error = await conn.receive("__error__")
        assert error["code"] == "RATE_LIMIT_ERROR"
