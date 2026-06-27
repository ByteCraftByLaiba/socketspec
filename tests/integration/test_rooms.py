# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import anyio

from socketspec.app import SocketApp
from socketspec.testing import TestClient


async def test_broadcast_reaches_room_members() -> None:
    app = SocketApp()

    @app.on("join")
    async def handle_join(conn: object, payload: dict[str, object]) -> None:
        await app.rooms.join(conn, "test_room")

    @app.on("shout")
    async def handle_shout(conn: object, payload: dict[str, str]) -> None:
        await app.rooms.broadcast("test_room", "shouted", payload)

    client = TestClient(app)
    async with client.connect() as sender, client.connect() as receiver:
        await receiver.emit("join", {})
        await sender.emit("join", {})
        await anyio.sleep(0.05)
        await sender.emit("shout", {"message": "hello"})
        await anyio.sleep(0.05)
        broadcast = await receiver.receive("shouted")
        assert broadcast["message"] == "hello"
