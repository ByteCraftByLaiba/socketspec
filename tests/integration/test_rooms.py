# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Integration tests for SocketSpec Room features and room hooks."""

from __future__ import annotations

import anyio
import pytest

from socketspec.app import SocketApp
from socketspec.connection import Connection
from socketspec.errors import RoomPermissionError
from socketspec.testing import TestClient


@pytest.mark.anyio
async def test_join_room_and_receive_broadcast() -> None:
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")

    client = TestClient(app)
    async with client.connect() as c1, client.connect() as c2:
        await c1.emit("join", {})
        await c2.emit("join", {})
        await anyio.sleep(0.05)

        await app.rooms.broadcast("lobby", "announce", {"msg": "hello"})
        m1 = await c1.receive("announce")
        m2 = await c2.receive("announce")
        assert m1["msg"] == "hello"
        assert m2["msg"] == "hello"


@pytest.mark.anyio
async def test_broadcast_does_not_reach_non_member() -> None:
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, payload["room"])

    client = TestClient(app)
    async with client.connect() as member, client.connect() as outsider:
        await member.emit("join", {"room": "general"})
        await outsider.emit("join", {"room": "lobby"})
        await anyio.sleep(0.05)

        await app.rooms.broadcast("general", "msg", {"text": "secret"})
        res = await member.receive("msg")
        assert res["text"] == "secret"

        with pytest.raises(TimeoutError):
            await outsider.receive("msg", timeout=0.2)


@pytest.mark.anyio
async def test_leave_room_stops_receiving_broadcast() -> None:
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")

    @app.on("leave")
    async def leave(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.leave(conn, "lobby")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("join", {})
        await anyio.sleep(0.02)
        await conn.emit("leave", {})
        await anyio.sleep(0.02)

        await app.rooms.broadcast("lobby", "msg", {"text": "hi"})
        with pytest.raises(TimeoutError):
            await conn.receive("msg", timeout=0.2)


@pytest.mark.anyio
async def test_broadcast_all_reaches_every_connected_client() -> None:
    app = SocketApp()

    client = TestClient(app)
    async with client.connect() as c1, client.connect() as c2:
        await app.rooms.broadcast_all("global", {"data": "system alert"})
        r1 = await c1.receive("global")
        r2 = await c2.receive("global")
        assert r1["data"] == "system alert"
        assert r2["data"] == "system alert"


@pytest.mark.anyio
async def test_broadcast_except_skips_sender() -> None:
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "chat")

    client = TestClient(app)
    async with client.connect() as sender, client.connect() as receiver:
        await sender.emit("join", {})
        await receiver.emit("join", {})
        await anyio.sleep(0.05)

        await app.rooms.broadcast(
            "chat",
            "msg",
            {"text": "from-sender"},
            exclude={sender.connection.id},
        )
        res = await receiver.receive("msg")
        assert res["text"] == "from-sender"

        with pytest.raises(TimeoutError):
            await sender.receive("msg", timeout=0.2)


@pytest.mark.anyio
async def test_room_guard_allows_permitted_connection() -> None:
    app = SocketApp()

    @app.room_guard("team:{team_id}")
    async def guard(conn: Connection, team_id: str) -> bool:
        return team_id == "eng"

    client = TestClient(app)
    async with client.connect() as conn:
        await app.rooms.join(conn.connection, "team:eng")
        assert "team:eng" in conn.connection.rooms


@pytest.mark.anyio
async def test_room_guard_rejects_unpermitted_connection() -> None:
    app = SocketApp()

    @app.room_guard("team:{team_id}")
    async def guard(conn: Connection, team_id: str) -> bool:
        return team_id == "eng"

    client = TestClient(app)
    async with client.connect() as conn:
        with pytest.raises(RoomPermissionError):
            await app.rooms.join(conn.connection, "team:sales")
        assert "team:sales" not in conn.connection.rooms


@pytest.mark.anyio
async def test_on_room_join_hook_fires() -> None:
    app = SocketApp()
    joins: list[str] = []

    @app.on_room_join
    async def join_hook(conn: Connection, room: str) -> None:
        joins.append(room)

    client = TestClient(app)
    async with client.connect() as conn:
        await app.rooms.join(conn.connection, "lobby")
        assert joins == ["lobby"]


@pytest.mark.anyio
async def test_on_room_leave_hook_fires() -> None:
    # room_leave hooks fire on disconnect, not on explicit rooms.leave().
    app = SocketApp()
    leaves: list[str] = []

    @app.on_room_leave
    async def leave_hook(conn: Connection, room: str) -> None:
        leaves.append(room)

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("join", {})
        await anyio.sleep(0.05)
    # disconnect triggers room_leave hooks for every room the conn was in
    assert "lobby" in leaves


@pytest.mark.anyio
async def test_disconnect_removes_from_all_rooms() -> None:
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "r1")
        await app.rooms.join(conn, "r2")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("join", {})
        await anyio.sleep(0.05)
        # Verify rooms assigned
        assert "r1" in conn.connection.rooms
        assert "r2" in conn.connection.rooms
        conn_id = conn.connection.id

    # Once closed, membership in backend should be gone
    members1 = await app.rooms.members("r1")
    members2 = await app.rooms.members("r2")
    assert not any(m.id == conn_id for m in members1)
    assert not any(m.id == conn_id for m in members2)


@pytest.mark.anyio
async def test_broadcast_continues_after_one_member_disconnects() -> None:
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")

    client = TestClient(app)

    # Connect both clients and both join the lobby
    async with client.connect() as conn1, client.connect() as conn2:
        await conn1.emit("join", {})
        await conn2.emit("join", {})
        await anyio.sleep(0.05)
        # conn2 disconnects first while conn1 is still active
        await conn2.connection.disconnect("test")
        await anyio.sleep(0.02)

        # Broadcast to lobby should still reach conn1
        await app.rooms.broadcast("lobby", "msg", {"data": 1})
        res = await conn1.receive("msg")
        assert res["data"] == 1


@pytest.mark.anyio
async def test_large_room_broadcast_chunked_correctly() -> None:
    # Set chunk size to 2 internally or simulate broadcasting to many members
    app = SocketApp()

    @app.on("join")
    async def join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")

    client = TestClient(app)
    # connect 5 clients
    async with (
        client.connect() as c1,
        client.connect() as c2,
        client.connect() as c3,
        client.connect() as c4,
        client.connect() as c5,
    ):
        for c in [c1, c2, c3, c4, c5]:
            await c.emit("join", {})
        await anyio.sleep(0.05)

        # Broadcast should reach all 5 even if internally processed in chunks
        await app.rooms.broadcast("lobby", "announce", {"test": "chunking"})
        for c in [c1, c2, c3, c4, c5]:
            res = await c.receive("announce")
            assert res["test"] == "chunking"
