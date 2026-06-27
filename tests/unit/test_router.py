# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import anyio

from socketspec.app import SocketApp
from socketspec.testing import TestClient


async def test_ordered_events_run_sequentially() -> None:
    app = SocketApp()
    results: list[int] = []

    @app.on("ordered", ordered=True)
    async def handle_ordered(conn: object, payload: dict[str, int]) -> None:
        results.append(payload["value"])
        await anyio.sleep(0.02)

    async with TestClient(app).connect() as conn:
        await conn.emit("ordered", {"value": 1})
        await conn.emit("ordered", {"value": 2})
        await anyio.sleep(0.1)
        assert results == [1, 2]
