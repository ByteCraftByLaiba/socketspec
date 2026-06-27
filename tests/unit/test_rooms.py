# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import pytest

from socketspec.backends.memory import MemoryBackend
from socketspec.errors import RoomPermissionError
from socketspec.manager import ConnectionManager
from socketspec.rooms import RoomManager
from tests.conftest import make_connection


async def test_join_adds_connection_to_members() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rooms = RoomManager(backend, manager)
    conn = make_connection("c1")
    await manager.connect(conn)
    await rooms.join(conn, "lobby")
    members = await rooms.members("lobby")
    assert len(members) == 1


async def test_leave_removes_connection_from_members() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rooms = RoomManager(backend, manager)
    conn = make_connection("c1")
    await manager.connect(conn)
    await rooms.join(conn, "lobby")
    await rooms.leave(conn, "lobby")
    assert await rooms.members("lobby") == []


async def test_broadcast_delivers_to_room_members() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rooms = RoomManager(backend, manager)
    conn = make_connection("c1")
    await manager.connect(conn)
    await rooms.join(conn, "lobby")
    await rooms.broadcast("lobby", "shouted", {"message": "hello"})
    message = conn.raw_socket.outgoing.get_nowait()
    assert message["payload"]["message"] == "hello"


async def test_broadcast_empty_room_does_not_raise() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rooms = RoomManager(backend, manager)
    await rooms.broadcast("empty", "event", {})


async def test_guard_rejection_raises_room_permission_error() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rooms = RoomManager(backend, manager)
    conn = make_connection("c1")
    await manager.connect(conn)

    async def deny(_conn: object, **_kwargs: object) -> bool:
        return False

    rooms.register_guard("private:{id}", deny)
    with pytest.raises(RoomPermissionError):
        await rooms.join(conn, "private:secret")
