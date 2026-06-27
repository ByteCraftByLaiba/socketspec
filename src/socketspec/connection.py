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

"""Data models for a live WebSocket connection and its identity.

Owns Connection, Identity, and SessionInfo dataclasses.
Does NOT own send logic, auth, rooms, or session lifecycle enforcement.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from socketspec.types import ConnectionId, EventName, Namespace, PayloadDict, RoomName

EmitCallable = Callable[[EventName, PayloadDict | BaseModel], Awaitable[None]]
DisconnectCallable = Callable[[str], Awaitable[None]]


@runtime_checkable
class RawSocket(Protocol):
    """Minimal interface adapters must provide on the underlying WebSocket."""

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON-serializable message frame to the client."""

    async def close(self, code: int = 1000) -> None:
        """Close the underlying WebSocket connection."""


@dataclass
class Identity:
    """Authentication result attached to a connection."""

    user_id: str | None = None
    scopes: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    raw_token: str | None = None
    token_expires_at: datetime | None = None


@dataclass
class SessionInfo:
    """Session TTL metadata for a connection."""

    started_at: datetime
    expires_at: datetime | None
    token_expires_at: datetime | None


@dataclass
class Connection:
    """A single live WebSocket connection passed to every event handler.

    Note:
        ``emit`` and ``disconnect`` are rebound by ``ConnectionManager.connect()``
        with bound callables. Until then, calling them raises ``RuntimeError``.
    """

    id: ConnectionId
    raw_socket: RawSocket
    identity: Identity
    session: SessionInfo
    connected_at: datetime
    last_active: datetime
    rooms: set[RoomName] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    namespace: Namespace = "/"
    _emit_fn: EmitCallable | None = field(default=None, repr=False, compare=False)
    _disconnect_fn: DisconnectCallable | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    async def emit(
        self,
        event: EventName,
        payload: PayloadDict | BaseModel,
    ) -> None:
        """Emit an event directly to this connection.

        Args:
            event: Target event name.
            payload: JSON-serializable payload dict or model dump.

        Raises:
            RuntimeError: If ``ConnectionManager.connect()`` has not run yet.
        """
        if self._emit_fn is None:
            raise RuntimeError(
                "Connection.emit is not available until "
                "ConnectionManager.connect() is called"
            )
        await self._emit_fn(event, payload)

    async def disconnect(self, reason: str = "server_close") -> None:
        """Forcibly close this connection.

        Args:
            reason: Human-readable disconnect reason for logging.

        Raises:
            RuntimeError: If ``ConnectionManager.connect()`` has not run yet.
        """
        if self._disconnect_fn is None:
            raise RuntimeError(
                "Connection.disconnect is not available until "
                "ConnectionManager.connect() is called"
            )
        await self._disconnect_fn(reason)
