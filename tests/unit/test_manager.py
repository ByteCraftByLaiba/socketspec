# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import pytest

from socketspec.backends.memory import MemoryBackend
from socketspec.errors import DuplicateConnectionError
from socketspec.manager import ConnectionManager
from tests.conftest import make_connection


async def test_connect_adds_connection_to_all() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    conn = make_connection("c1")
    await manager.connect(conn)
    assert len(await manager.all()) == 1


async def test_disconnect_removes_connection_from_all() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    conn = make_connection("c1")
    await manager.connect(conn)
    await manager.disconnect(conn)
    assert await manager.all() == []


async def test_send_delivers_message_to_existing_connection() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    conn = make_connection("c1")
    await manager.connect(conn)
    await manager.send("c1", "hello", {"text": "hi"})
    message = conn.raw_socket.outgoing.get_nowait()
    assert message["event"] == "hello"


async def test_send_to_missing_connection_does_not_raise() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    await manager.send("missing", "hello", {})


async def test_connect_duplicate_id_raises_duplicate_connection_error() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    conn_a = make_connection("same-id")
    conn_b = make_connection("same-id")
    await manager.connect(conn_a)
    with pytest.raises(DuplicateConnectionError):
        await manager.connect(conn_b)
