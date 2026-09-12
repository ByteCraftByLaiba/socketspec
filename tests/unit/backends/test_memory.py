# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for SocketSpec in-memory backend — all methods and concurrency."""

from __future__ import annotations

import asyncio

import pytest

from socketspec.backends.memory import MemoryBackend


@pytest.fixture
def backend() -> MemoryBackend:
    return MemoryBackend()


# ── Connection management ─────────────────────────────────────────────────────


async def test_store_connection_makes_it_findable(backend: MemoryBackend) -> None:
    await backend.store_connection("c1", {"user_id": "u1"})
    assert await backend.connection_exists("c1")


async def test_remove_connection_cleans_up_completely(backend: MemoryBackend) -> None:
    await backend.store_connection("c1", {})
    await backend.remove_connection("c1")
    assert not await backend.connection_exists("c1")


async def test_connection_exists_returns_true_when_present(
    backend: MemoryBackend,
) -> None:
    await backend.store_connection("cx", {})
    assert await backend.connection_exists("cx") is True


async def test_connection_exists_returns_false_when_absent(
    backend: MemoryBackend,
) -> None:
    assert await backend.connection_exists("no-such") is False


async def test_remove_nonexistent_connection_does_not_raise(
    backend: MemoryBackend,
) -> None:
    await backend.remove_connection("ghost")  # must not raise


# ── Room management ───────────────────────────────────────────────────────────


async def test_add_to_room_adds_connection(backend: MemoryBackend) -> None:
    await backend.add_to_room("c1", "general")
    members = await backend.get_room_members("general")
    assert "c1" in members


async def test_get_room_members_returns_correct_members(backend: MemoryBackend) -> None:
    await backend.add_to_room("a", "room1")
    await backend.add_to_room("b", "room1")
    members = await backend.get_room_members("room1")
    assert set(members) == {"a", "b"}


async def test_remove_from_room_removes_connection(backend: MemoryBackend) -> None:
    await backend.add_to_room("c1", "room1")
    await backend.remove_from_room("c1", "room1")
    members = await backend.get_room_members("room1")
    assert "c1" not in members


async def test_room_destroyed_when_last_member_leaves(backend: MemoryBackend) -> None:
    await backend.add_to_room("c1", "temp-room")
    await backend.remove_from_room("c1", "temp-room")
    members = await backend.get_room_members("temp-room")
    assert members == []


async def test_get_connection_rooms_returns_all_rooms(backend: MemoryBackend) -> None:
    await backend.add_to_room("c1", "r1")
    await backend.add_to_room("c1", "r2")
    rooms = await backend.get_connection_rooms("c1")
    assert set(rooms) >= {"r1", "r2"}


async def test_remove_connection_cleans_up_room_membership(
    backend: MemoryBackend,
) -> None:
    # store_connection FIRST, then join room — order matters!
    await backend.store_connection("c1", {})
    await backend.add_to_room("c1", "lobby")
    await backend.remove_connection("c1")
    members = await backend.get_room_members("lobby")
    assert "c1" not in members


async def test_remove_connection_destroys_empty_rooms(backend: MemoryBackend) -> None:
    # store_connection FIRST, then join room
    await backend.store_connection("only", {})
    await backend.add_to_room("only", "solo-room")
    await backend.remove_connection("only")
    assert await backend.get_room_members("solo-room") == []


async def test_connection_can_join_multiple_rooms(backend: MemoryBackend) -> None:
    for r in ["r1", "r2", "r3"]:
        await backend.add_to_room("c1", r)
    rooms = await backend.get_connection_rooms("c1")
    assert len(rooms) >= 3


async def test_get_room_members_returns_empty_for_unknown_room(
    backend: MemoryBackend,
) -> None:
    members = await backend.get_room_members("does-not-exist")
    assert members == []


# ── Pub/Sub ───────────────────────────────────────────────────────────────────


async def test_subscribe_receives_published_messages(backend: MemoryBackend) -> None:
    received: list[dict] = []  # type: ignore[type-arg]

    async def handler(msg: dict) -> None:  # type: ignore[type-arg]
        received.append(msg)

    await backend.subscribe("events", handler)
    await backend.publish("events", {"type": "test"})
    assert len(received) == 1
    assert received[0]["type"] == "test"


async def test_publish_to_unsubscribed_channel_does_not_raise(
    backend: MemoryBackend,
) -> None:
    await backend.publish("no-subscribers", {"data": 1})  # must not raise


async def test_unsubscribe_stops_receiving_messages(backend: MemoryBackend) -> None:
    received: list[dict] = []  # type: ignore[type-arg]

    async def handler(msg: dict) -> None:  # type: ignore[type-arg]
        received.append(msg)

    await backend.subscribe("ch", handler)
    # unsubscribe takes only a channel name — removes all subscribers
    await backend.unsubscribe("ch")
    await backend.publish("ch", {"x": 1})
    assert received == []


async def test_multiple_subscribers_on_same_channel_all_receive(
    backend: MemoryBackend,
) -> None:
    results: list[str] = []

    async def h1(msg: dict) -> None:  # type: ignore[type-arg]
        results.append("h1")

    async def h2(msg: dict) -> None:  # type: ignore[type-arg]
        results.append("h2")

    await backend.subscribe("shared", h1)
    await backend.subscribe("shared", h2)
    await backend.publish("shared", {})
    assert "h1" in results
    assert "h2" in results


# ── Close ─────────────────────────────────────────────────────────────────────


async def test_close_clears_all_state(backend: MemoryBackend) -> None:
    await backend.store_connection("c1", {})
    await backend.add_to_room("c1", "r1")
    await backend.close()
    assert not await backend.connection_exists("c1")
    assert await backend.get_room_members("r1") == []


async def test_close_is_idempotent(backend: MemoryBackend) -> None:
    await backend.close()
    await backend.close()  # must not raise


# ── Concurrency ───────────────────────────────────────────────────────────────


async def test_concurrent_connects_do_not_corrupt_state(backend: MemoryBackend) -> None:
    async def add(conn_id: str) -> None:
        await backend.store_connection(conn_id, {"user_id": conn_id})

    await asyncio.gather(*[add(f"c{i}") for i in range(20)])
    for i in range(20):
        assert await backend.connection_exists(f"c{i}")


async def test_concurrent_room_joins_do_not_corrupt_state(
    backend: MemoryBackend,
) -> None:
    await asyncio.gather(*[backend.add_to_room(f"c{i}", "lobby") for i in range(20)])
    members = await backend.get_room_members("lobby")
    assert len(members) == 20


async def test_concurrent_disconnects_do_not_raise(backend: MemoryBackend) -> None:
    for i in range(10):
        await backend.store_connection(f"c{i}", {})
    await asyncio.gather(*[backend.remove_connection(f"c{i}") for i in range(10)])
