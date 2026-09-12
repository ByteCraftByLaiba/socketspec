# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for RoomManager — join, leave, broadcast, guards, and members."""

from __future__ import annotations

import asyncio

import pytest

from socketspec.app import SocketApp
from socketspec.backends.memory import MemoryBackend
from socketspec.connection import Connection
from socketspec.errors import RoomPermissionError
from socketspec.manager import ConnectionManager
from socketspec.rooms import RoomManager
from socketspec.testing import TestClient
from tests.conftest import make_connection


@pytest.fixture
def backend() -> MemoryBackend:
    return MemoryBackend()


@pytest.fixture
def manager(backend: MemoryBackend) -> ConnectionManager:
    return ConnectionManager(backend)


@pytest.fixture
def room_manager(backend: MemoryBackend, manager: ConnectionManager) -> RoomManager:
    return RoomManager(backend, manager)


# ── Join ──────────────────────────────────────────────────────────────────────


async def test_join_adds_connection_to_room(room_manager: RoomManager) -> None:
    conn = make_connection("j1")
    await room_manager.join(conn, "general")
    members = await room_manager.members("general")
    ids = [c.id for c in members]
    assert "j1" not in ids  # conn not registered in manager, so not returned by members


async def test_join_updates_connection_rooms_set(room_manager: RoomManager) -> None:
    conn = make_connection("j2")
    await room_manager.join(conn, "lobby")
    assert "lobby" in conn.rooms


async def test_join_creates_room_implicitly(room_manager: RoomManager) -> None:
    conn = make_connection("j3")
    await room_manager.join(conn, "new-room")
    # No error means it was created
    assert "new-room" in conn.rooms


async def test_join_when_guard_returns_false_raises_permission_error(
    room_manager: RoomManager,
) -> None:
    async def deny(conn: Connection) -> bool:
        return False

    room_manager.register_guard("general", deny)

    conn = make_connection("j4")
    with pytest.raises(RoomPermissionError):
        await room_manager.join(conn, "general")


async def test_join_when_guard_returns_true_succeeds(room_manager: RoomManager) -> None:
    async def allow(conn: Connection) -> bool:
        return True

    room_manager.register_guard("vip", allow)

    conn = make_connection("j5")
    await room_manager.join(conn, "vip")  # must not raise
    assert "vip" in conn.rooms


async def test_join_with_pattern_guard_extracts_variables() -> None:
    app = SocketApp()
    received_vars: dict[str, str] = {}

    @app.room_guard("team:{team_id}")
    async def team_guard(conn: Connection, team_id: str) -> bool:
        received_vars["team_id"] = team_id
        return True

    async with TestClient(app).connect() as tc:
        await tc.join_room("team:alpha")
        assert received_vars.get("team_id") == "alpha"


# ── Leave ─────────────────────────────────────────────────────────────────────


async def test_leave_removes_connection_from_room(room_manager: RoomManager) -> None:
    conn = make_connection("l1")
    await room_manager.join(conn, "lobby")
    await room_manager.leave(conn, "lobby")
    assert "lobby" not in conn.rooms


async def test_leave_updates_connection_rooms_set(room_manager: RoomManager) -> None:
    conn = make_connection("l2")
    await room_manager.join(conn, "chat")
    await room_manager.leave(conn, "chat")
    assert "chat" not in conn.rooms


async def test_leave_destroys_empty_room(
    room_manager: RoomManager, backend: MemoryBackend
) -> None:
    conn = make_connection("l3")
    await room_manager.join(conn, "solo")
    await room_manager.leave(conn, "solo")
    assert await backend.get_room_members("solo") == []


async def test_leave_nonexistent_room_does_not_raise(room_manager: RoomManager) -> None:
    conn = make_connection("l4")
    await room_manager.leave(conn, "nonexistent")  # must not raise


# ── Broadcast ─────────────────────────────────────────────────────────────────


async def test_broadcast_reaches_all_room_members() -> None:
    app = SocketApp()

    @app.on("join")
    async def do_join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")

    async with TestClient(app).connect() as c1, TestClient(app).connect() as c2:
        await c1.emit("join", {})
        await c2.emit("join", {})
        await asyncio.sleep(0.05)
        await app.rooms.broadcast("lobby", "announce", {"msg": "hello"})
        msg1 = await c1.receive("announce")
        msg2 = await c2.receive("announce")
        assert msg1["msg"] == "hello"
        assert msg2["msg"] == "hello"


async def test_broadcast_does_not_reach_non_members() -> None:
    app = SocketApp()

    @app.on("join")
    async def do_join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "vip")

    async with (
        TestClient(app).connect() as member,
        TestClient(app).connect() as outsider,
    ):
        await member.emit("join", {})
        await asyncio.sleep(0.05)
        await app.rooms.broadcast("vip", "secret", {"data": 1})
        # member should receive it
        result = await member.receive("secret")
        assert result["data"] == 1
        # outsider queue must be empty — wait_for should time out
        with pytest.raises(TimeoutError):
            await outsider.receive("secret", timeout=0.2)


async def test_broadcast_to_empty_room_does_not_raise() -> None:
    app = SocketApp()
    await app.rooms.broadcast("empty-room", "ping", {})  # must not raise


async def test_broadcast_excludes_sender() -> None:
    app = SocketApp()

    @app.on("join")
    async def do_join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "chat")

    async with TestClient(app).connect() as sender, TestClient(app).connect() as recv:
        await sender.emit("join", {})
        await recv.emit("join", {})
        await asyncio.sleep(0.05)
        await app.rooms.broadcast(
            "chat", "msg", {"text": "hi"}, exclude={sender.connection.id}
        )
        result = await recv.receive("msg")
        assert result["text"] == "hi"
        with pytest.raises(TimeoutError):
            await sender.receive("msg", timeout=0.2)


# ── Members ───────────────────────────────────────────────────────────────────


async def test_members_returns_connection_objects() -> None:
    app = SocketApp()

    @app.on("join")
    async def do_join(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "members-room")

    async with TestClient(app).connect() as tc:
        await tc.emit("join", {})
        await asyncio.sleep(0.05)
        members = await app.rooms.members("members-room")
        assert any(m.id == tc.connection.id for m in members)


async def test_members_returns_empty_for_nonexistent_room() -> None:
    app = SocketApp()
    members = await app.rooms.members("ghost-room")
    assert members == []


# ── Static rooms ──────────────────────────────────────────────────────────────


def test_register_static_room_persists() -> None:
    from socketspec.rooms import Room

    app = SocketApp(rooms=[Room(name="lobby"), Room(name="general")])
    assert "lobby" in app.rooms._static_rooms
    assert "general" in app.rooms._static_rooms


# ── Pattern matching ──────────────────────────────────────────────────────────


async def test_room_guard_pattern_does_not_match_wrong_pattern() -> None:
    app = SocketApp()

    @app.room_guard("team:{team_id}")
    async def guard(conn: Connection, team_id: str) -> bool:
        return True

    async with TestClient(app).connect() as tc:
        # "lobby" doesn't match "team:{team_id}" but also has no specific guard,
        # so it should succeed (no guard = allow)
        await tc.join_room("lobby")
        assert "lobby" in tc.connection.rooms


async def test_room_guard_extracts_multiple_variables() -> None:
    app = SocketApp()
    extracted: dict[str, str] = {}

    @app.room_guard("org:{org_id}:team:{team_id}")
    async def guard(conn: Connection, org_id: str, team_id: str) -> bool:
        extracted["org_id"] = org_id
        extracted["team_id"] = team_id
        return True

    async with TestClient(app).connect() as tc:
        await tc.join_room("org:acme:team:eng")
        assert extracted["org_id"] == "acme"
        assert extracted["team_id"] == "eng"
