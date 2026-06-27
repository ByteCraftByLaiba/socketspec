# Copyright (c) 2025 Laiba Shahab. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""In-process storage backend for single-server SocketSpec deployments.

Owns in-memory connection, room, and pub/sub state.
Does NOT own Connection objects or cross-process communication.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from socketspec.types import ConnectionId, RoomName

logger = logging.getLogger(__name__)

PubSubCallback = Callable[[dict[str, Any]], Awaitable[None]]


class MemoryBackend:
    """Default backend storing all state in the current process.

    Note:
        All mutations are protected by a single ``asyncio.Lock``.
    """

    def __init__(self) -> None:
        self._connections: dict[ConnectionId, dict[str, Any]] = {}
        self._rooms: dict[RoomName, set[ConnectionId]] = {}
        self._conn_rooms: dict[ConnectionId, set[RoomName]] = {}
        self._subscribers: dict[str, list[PubSubCallback]] = {}
        self._lock = asyncio.Lock()

    async def store_connection(self, id: ConnectionId, meta: dict[str, Any]) -> None:
        """Store connection metadata and initialize its room set."""
        async with self._lock:
            self._connections[id] = meta
            self._conn_rooms[id] = set()

    async def remove_connection(self, id: ConnectionId) -> None:
        """Remove a connection and clean up all room memberships."""
        async with self._lock:
            self._connections.pop(id, None)
            rooms = self._conn_rooms.pop(id, set())
            for room in rooms:
                members = self._rooms.get(room)
                if members is None:
                    continue
                members.discard(id)
                if not members:
                    self._rooms.pop(room, None)

    async def connection_exists(self, id: ConnectionId) -> bool:
        """Return whether the connection id exists in storage."""
        async with self._lock:
            return id in self._connections

    async def get_room_members(self, room: RoomName) -> list[ConnectionId]:
        """Return a snapshot of connection ids in the given room."""
        async with self._lock:
            return list(self._rooms.get(room, set()))

    async def add_to_room(self, id: ConnectionId, room: RoomName) -> None:
        """Add a connection to a room."""
        async with self._lock:
            if room not in self._rooms:
                self._rooms[room] = set()
            self._rooms[room].add(id)
            self._conn_rooms.setdefault(id, set()).add(room)

    async def remove_from_room(self, id: ConnectionId, room: RoomName) -> None:
        """Remove a connection from a room."""
        async with self._lock:
            members = self._rooms.get(room)
            if members is not None:
                members.discard(id)
                if not members:
                    self._rooms.pop(room, None)
            conn_rooms = self._conn_rooms.get(id)
            if conn_rooms is not None:
                conn_rooms.discard(room)

    async def get_connection_rooms(self, id: ConnectionId) -> list[RoomName]:
        """Return all rooms the connection belongs to."""
        async with self._lock:
            return list(self._conn_rooms.get(id, set()))

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Deliver a message to all in-process subscribers on a channel."""
        callbacks = list(self._subscribers.get(channel, []))
        for callback in callbacks:
            try:
                await callback(message)
            except Exception:
                logger.error(
                    "Pub/sub callback failed on channel %s",
                    channel,
                    exc_info=True,
                )

    async def subscribe(
        self,
        channel: str,
        callback: PubSubCallback,
    ) -> None:
        """Register a callback for messages on a channel."""
        self._subscribers.setdefault(channel, []).append(callback)

    async def unsubscribe(self, channel: str) -> None:
        """Remove all subscribers from a channel."""
        self._subscribers.pop(channel, None)

    async def close(self) -> None:
        """Clear all in-memory backend state."""
        async with self._lock:
            self._connections.clear()
            self._rooms.clear()
            self._conn_rooms.clear()
            self._subscribers.clear()
