# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for ConnectionManager — registration, delivery, and concurrency."""

from __future__ import annotations

import asyncio

import pytest

from socketspec.backends.memory import MemoryBackend
from socketspec.manager import ConnectionManager
from tests.conftest import make_connection


@pytest.fixture
def backend() -> MemoryBackend:
    return MemoryBackend()


@pytest.fixture
def manager(backend: MemoryBackend) -> ConnectionManager:
    return ConnectionManager(backend)


# ── Connect ───────────────────────────────────────────────────────────────────


async def test_connect_registers_connection(manager: ConnectionManager) -> None:
    conn = make_connection("c1")
    await manager.connect(conn)
    assert await manager.get("c1") is conn


async def test_connect_injects_emit_callable_into_connection(
    manager: ConnectionManager,
) -> None:
    conn = make_connection("c2")
    await manager.connect(conn)
    assert conn._emit_fn is not None


async def test_connect_injects_disconnect_callable_into_connection(
    manager: ConnectionManager,
) -> None:
    conn = make_connection("c3")
    await manager.connect(conn)
    assert conn._disconnect_fn is not None


async def test_connect_stores_metadata_in_backend(
    manager: ConnectionManager, backend: MemoryBackend
) -> None:
    conn = make_connection("c4", user_id="alice")
    await manager.connect(conn)
    assert await backend.connection_exists("c4")


async def test_connect_duplicate_id_raises(manager: ConnectionManager) -> None:
    from socketspec.errors import DuplicateConnectionError

    conn = make_connection("dup")
    await manager.connect(conn)
    conn2 = make_connection("dup")
    with pytest.raises(DuplicateConnectionError):
        await manager.connect(conn2)


# ── Disconnect ────────────────────────────────────────────────────────────────


async def test_disconnect_removes_connection(manager: ConnectionManager) -> None:
    conn = make_connection("c5")
    await manager.connect(conn)
    await manager.disconnect(conn)
    assert await manager.get("c5") is None


async def test_disconnect_cleans_up_backend(
    manager: ConnectionManager, backend: MemoryBackend
) -> None:
    conn = make_connection("c6")
    await manager.connect(conn)
    await manager.disconnect(conn)
    assert not await backend.connection_exists("c6")


async def test_disconnect_nonexistent_connection_does_not_raise(
    manager: ConnectionManager,
) -> None:
    conn = make_connection("ghost")
    # disconnect without connecting first — must not raise
    await manager.disconnect(conn)


# ── Get ───────────────────────────────────────────────────────────────────────


async def test_get_returns_connection_when_present(manager: ConnectionManager) -> None:
    conn = make_connection("c7")
    await manager.connect(conn)
    result = await manager.get("c7")
    assert result is conn


async def test_get_returns_none_when_absent(manager: ConnectionManager) -> None:
    result = await manager.get("nobody")
    assert result is None


# ── All ───────────────────────────────────────────────────────────────────────


async def test_all_returns_all_connected(manager: ConnectionManager) -> None:
    c1 = make_connection("a1")
    c2 = make_connection("a2")
    await manager.connect(c1)
    await manager.connect(c2)
    all_conns = await manager.all()
    ids = {c.id for c in all_conns}
    assert {"a1", "a2"} <= ids


async def test_all_returns_empty_when_no_connections(
    manager: ConnectionManager,
) -> None:
    assert await manager.all() == []


# ── Send ──────────────────────────────────────────────────────────────────────


async def test_send_delivers_correct_envelope(manager: ConnectionManager) -> None:
    conn = make_connection("s1")
    await manager.connect(conn)
    await manager.send("s1", "welcome", {"msg": "hi"})
    # TestRawSocket queues outgoing frames
    from socketspec.testing import TestRawSocket

    assert isinstance(conn.raw_socket, TestRawSocket)
    frame = await conn.raw_socket.outgoing.get()
    assert frame["event"] == "welcome"
    assert frame["payload"]["msg"] == "hi"


async def test_send_to_nonexistent_connection_does_not_raise(
    manager: ConnectionManager,
) -> None:
    await manager.send("nobody", "ping", {})  # must not raise


async def test_send_silently_handles_dead_socket(manager: ConnectionManager) -> None:
    conn = make_connection("dead")
    await manager.connect(conn)
    conn.raw_socket.closed = True  # type: ignore[attr-defined]
    # Should not raise even if socket is "closed"
    await manager.send("dead", "event", {})


async def test_send_pydantic_model_serialized(manager: ConnectionManager) -> None:
    from pydantic import BaseModel

    class Reply(BaseModel):
        ok: bool

    conn = make_connection("pm1")
    await manager.connect(conn)
    await manager.send("pm1", "reply", Reply(ok=True))
    from socketspec.testing import TestRawSocket

    assert isinstance(conn.raw_socket, TestRawSocket)
    frame = await conn.raw_socket.outgoing.get()
    assert frame["payload"]["ok"] is True


# ── Injected emit ─────────────────────────────────────────────────────────────


async def test_injected_emit_sends_correct_event(manager: ConnectionManager) -> None:
    conn = make_connection("e1")
    await manager.connect(conn)
    await conn.emit("pong", {"ts": 123})
    from socketspec.testing import TestRawSocket

    assert isinstance(conn.raw_socket, TestRawSocket)
    frame = await conn.raw_socket.outgoing.get()
    assert frame["event"] == "pong"


async def test_injected_emit_formats_envelope_correctly(
    manager: ConnectionManager,
) -> None:
    conn = make_connection("e2")
    await manager.connect(conn)
    await conn.emit("reply", {"status": "ok"})
    from socketspec.testing import TestRawSocket

    assert isinstance(conn.raw_socket, TestRawSocket)
    frame = await conn.raw_socket.outgoing.get()
    assert "event" in frame
    assert "payload" in frame


# ── Injected disconnect ───────────────────────────────────────────────────────


async def test_injected_disconnect_removes_connection(
    manager: ConnectionManager,
) -> None:
    conn = make_connection("d1")
    await manager.connect(conn)
    await conn.disconnect("test_reason")
    assert await manager.get("d1") is None


# ── Concurrency ───────────────────────────────────────────────────────────────


async def test_concurrent_connects_all_registered(manager: ConnectionManager) -> None:
    conns = [make_connection(f"cc{i}") for i in range(10)]
    await asyncio.gather(*[manager.connect(c) for c in conns])
    all_conns = await manager.all()
    assert len(all_conns) == 10


async def test_concurrent_sends_all_delivered(manager: ConnectionManager) -> None:
    conn = make_connection("cs1")
    await manager.connect(conn)
    await asyncio.gather(*[manager.send("cs1", "ping", {"i": i}) for i in range(5)])
    from socketspec.testing import TestRawSocket

    assert isinstance(conn.raw_socket, TestRawSocket)
    assert conn.raw_socket.outgoing.qsize() == 5
