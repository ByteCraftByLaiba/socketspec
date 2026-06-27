# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from socketspec.backends.memory import MemoryBackend


async def test_store_and_remove_connection(memory_backend: MemoryBackend) -> None:
    await memory_backend.store_connection("c1", {"user_id": "u1"})
    assert await memory_backend.connection_exists("c1") is True
    await memory_backend.remove_connection("c1")
    assert await memory_backend.connection_exists("c1") is False


async def test_room_membership_tracks_connections(
    memory_backend: MemoryBackend,
) -> None:
    await memory_backend.store_connection("c1", {})
    await memory_backend.add_to_room("c1", "room-a")
    members = await memory_backend.get_room_members("room-a")
    assert members == ["c1"]
    await memory_backend.remove_from_room("c1", "room-a")
    assert await memory_backend.get_room_members("room-a") == []


async def test_publish_delivers_to_subscriber(memory_backend: MemoryBackend) -> None:
    received: list[dict[str, str]] = []

    async def callback(message: dict[str, str]) -> None:
        received.append(message)

    await memory_backend.subscribe("channel", callback)
    await memory_backend.publish("channel", {"event": "test"})
    assert received == [{"event": "test"}]
