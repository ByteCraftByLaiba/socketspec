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

"""Room membership, guards, and chunked broadcasting.

Owns room join/leave/broadcast on top of the storage backend.
Does NOT own connection registration or event routing.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from socketspec.backends.base import BackendAdapter
from socketspec.connection import Connection
from socketspec.errors import RoomPermissionError
from socketspec.manager import ConnectionManager
from socketspec.types import ConnectionId, EventName, PayloadDict, RoomName

logger = logging.getLogger(__name__)

# Prevents asyncio.gather memory spikes on very large rooms.
BROADCAST_CHUNK_SIZE = 500

RoomGuardFunc = Callable[..., Awaitable[bool]]
RoomJoinHook = Callable[[Connection, RoomName], Awaitable[None]]


@dataclass
class _RegisteredGuard:
    pattern: str
    guard: RoomGuardFunc


@dataclass
class Room:
    """Static room configuration registered at application startup."""

    name: RoomName
    private: bool = False
    max_members: int = 0
    ttl: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class RoomManager:
    """Manages room membership and broadcasts to room members."""

    def __init__(
        self,
        backend: BackendAdapter,
        manager: ConnectionManager,
    ) -> None:
        self._backend = backend
        self._manager = manager
        self._guards: list[_RegisteredGuard] = []
        self._static_rooms: set[RoomName] = set()
        self._join_hooks: list[RoomJoinHook] = []

    def register_join_hook(self, hook: RoomJoinHook) -> None:
        """Register a callback invoked after a successful room join."""
        self._join_hooks.append(hook)

    def register_guard(self, pattern: str, guard: RoomGuardFunc) -> None:
        """Register a permission guard for a room name pattern.

        Args:
            pattern: Room pattern such as ``chat:{room_id}``.
            guard: Async callable returning True when join is allowed.
        """
        self._guards.append(_RegisteredGuard(pattern=pattern, guard=guard))

    def register_static(self, room: RoomName) -> None:
        """Register a room that always exists even when empty."""
        self._static_rooms.add(room)

    async def join(self, conn: Connection, room: RoomName) -> None:
        """Add a connection to a room after optional guard checks.

        Args:
            conn: The connection joining the room.
            room: Target room name.

        Raises:
            RoomPermissionError: If a matching guard rejects the join.
        """
        registered = self._match_guard(room)
        if registered is not None:
            variables = self._extract_variables(registered.pattern, room)
            if variables is None:
                raise RoomPermissionError(f"Access denied to room '{room}'")
            allowed = await registered.guard(conn, **variables)
            if not allowed:
                raise RoomPermissionError(f"Access denied to room '{room}'")

        await self._backend.add_to_room(conn.id, room)
        conn.rooms.add(room)
        logger.info("Connection %s joined room %s", conn.id, room)
        for hook in self._join_hooks:
            await hook(conn, room)

    async def leave(self, conn: Connection, room: RoomName) -> None:
        """Remove a connection from a room.

        Args:
            conn: The connection leaving the room.
            room: Room name to leave.
        """
        await self._backend.remove_from_room(conn.id, room)
        conn.rooms.discard(room)
        logger.info("Connection %s left room %s", conn.id, room)

    async def broadcast(
        self,
        room: RoomName,
        event: EventName,
        payload: PayloadDict | BaseModel,
    ) -> None:
        """Broadcast an event to all members of a room in chunks.

        Args:
            room: Room name to broadcast to.
            event: Event name for the wire envelope.
            payload: JSON-serializable payload or Pydantic model.
        """
        member_ids = await self._backend.get_room_members(room)
        if not member_ids:
            return
        for chunk in self._chunks(member_ids, BROADCAST_CHUNK_SIZE):
            await asyncio.gather(
                *[self._safe_send(conn_id, event, payload) for conn_id in chunk]
            )

    async def broadcast_all(
        self,
        event: EventName,
        payload: PayloadDict | BaseModel,
    ) -> None:
        """Broadcast an event to every connected client."""
        all_conns = await self._manager.all()
        conn_ids = [conn.id for conn in all_conns]
        for chunk in self._chunks(conn_ids, BROADCAST_CHUNK_SIZE):
            await asyncio.gather(
                *[self._safe_send(conn_id, event, payload) for conn_id in chunk]
            )

    async def broadcast_except(
        self,
        exclude_id: ConnectionId,
        event: EventName,
        payload: PayloadDict | BaseModel,
    ) -> None:
        """Broadcast an event to all connections except one."""
        all_conns = await self._manager.all()
        targets = [conn.id for conn in all_conns if conn.id != exclude_id]
        for chunk in self._chunks(targets, BROADCAST_CHUNK_SIZE):
            await asyncio.gather(
                *[self._safe_send(conn_id, event, payload) for conn_id in chunk]
            )

    async def members(self, room: RoomName) -> list[Connection]:
        """Return live connections currently in a room."""
        member_ids = await self._backend.get_room_members(room)
        connections: list[Connection] = []
        for conn_id in member_ids:
            conn = await self._manager.get(conn_id)
            if conn is not None:
                connections.append(conn)
        return connections

    async def _safe_send(
        self,
        conn_id: ConnectionId,
        event: EventName,
        payload: PayloadDict | BaseModel,
    ) -> None:
        try:
            await self._manager.send(conn_id, event, payload)
        except Exception:
            logger.debug("Dead connection %s skipped during broadcast", conn_id)

    def _match_guard(self, room: RoomName) -> _RegisteredGuard | None:
        for registered in self._guards:
            if self._extract_variables(registered.pattern, room) is not None:
                return registered
        return None

    @staticmethod
    def _extract_variables(pattern: str, room: str) -> dict[str, str] | None:
        regex_parts: list[str] = []
        index = 0
        for match in re.finditer(r"\{(\w+)\}", pattern):
            regex_parts.append(re.escape(pattern[index : match.start()]))
            var_name = match.group(1)
            regex_parts.append(f"(?P<{var_name}>[^/]+)")
            index = match.end()
        regex_parts.append(re.escape(pattern[index:]))
        regex = "^" + "".join(regex_parts) + "$"
        matched = re.fullmatch(regex, room)
        if matched is None:
            return None
        return matched.groupdict()

    @staticmethod
    def _chunks(items: list[ConnectionId], size: int) -> list[list[ConnectionId]]:
        return [items[i : i + size] for i in range(0, len(items), size)]
