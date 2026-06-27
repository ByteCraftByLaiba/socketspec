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

"""Protocol definition for all SocketSpec storage backends.

Owns the BackendAdapter protocol only. Does NOT own any implementation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from socketspec.types import ConnectionId, RoomName


@runtime_checkable
class BackendAdapter(Protocol):
    """Contract implemented by in-process and distributed storage backends."""

    async def store_connection(self, id: ConnectionId, meta: dict[str, Any]) -> None:
        """Persist connection metadata for cross-process lookup."""

    async def remove_connection(self, id: ConnectionId) -> None:
        """Remove connection metadata and clean up room membership."""

    async def connection_exists(self, id: ConnectionId) -> bool:
        """Return whether a connection id is currently stored."""

    async def get_room_members(self, room: RoomName) -> list[ConnectionId]:
        """Return all connection ids in a room."""

    async def add_to_room(self, id: ConnectionId, room: RoomName) -> None:
        """Add a connection to a room."""

    async def remove_from_room(self, id: ConnectionId, room: RoomName) -> None:
        """Remove a connection from a room."""

    async def get_connection_rooms(self, id: ConnectionId) -> list[RoomName]:
        """Return all rooms a connection belongs to."""

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish a message to a pub/sub channel."""

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register a callback for messages on a pub/sub channel."""

    async def unsubscribe(self, channel: str) -> None:
        """Remove all subscribers from a pub/sub channel."""

    async def close(self) -> None:
        """Release backend resources on application shutdown."""
