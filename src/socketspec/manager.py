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

"""Owns all live WebSocket connections and their send capabilities.

Single source of truth for connection state. Does NOT own auth, rooms,
or session lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from socketspec.backends.base import BackendAdapter
from socketspec.connection import Connection
from socketspec.errors import DuplicateConnectionError
from socketspec.types import ConnectionId, EventName, PayloadDict

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registers connections and delivers outbound messages.

    Note:
        All state mutations are protected by ``asyncio.Lock``.
    """

    def __init__(self, backend: BackendAdapter) -> None:
        self._backend = backend
        self._connections: dict[ConnectionId, Connection] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        conn: Connection,
        full_lifecycle: Callable[[Connection, str], Awaitable[None]] | None = None,
    ) -> None:
        """Register a connection and inject ``emit`` / ``disconnect`` callables.

        Args:
            conn: Connection built by the framework adapter.
            full_lifecycle: Optional callback (e.g. ``app.handle_disconnect``)
                invoked on server-initiated disconnects so that all lifecycle
                hooks, room leave, session stop, and router cleanup run.

        Raises:
            DuplicateConnectionError: If a connection with the same id exists.
        """
        async with self._lock:
            if conn.id in self._connections:
                raise DuplicateConnectionError(
                    f"Connection id '{conn.id}' is already registered."
                )
            self._connections[conn.id] = conn

        await self._backend.store_connection(
            conn.id,
            {
                "user_id": conn.identity.user_id,
                "namespace": conn.namespace,
                "connected_at": conn.connected_at.isoformat(),
            },
        )
        conn._emit_fn = self._make_emitter(conn)
        conn._disconnect_fn = self._make_disconnector(conn, full_lifecycle)

    async def disconnect(self, conn: Connection) -> None:
        """Remove a connection from local and backend storage.

        Args:
            conn: The connection to unregister.
        """
        async with self._lock:
            self._connections.pop(conn.id, None)
        await self._backend.remove_connection(conn.id)

    async def get(self, conn_id: ConnectionId) -> Connection | None:
        """Return a connection by id, if still connected."""
        async with self._lock:
            return self._connections.get(conn_id)

    async def all(self) -> list[Connection]:
        """Return a snapshot of all live connections."""
        async with self._lock:
            return list(self._connections.values())

    async def send(
        self,
        conn_id: ConnectionId,
        event: EventName,
        payload: PayloadDict | BaseModel,
    ) -> None:
        """Deliver a message envelope to one connection.

        Args:
            conn_id: Target connection id.
            event: Event name for the wire envelope.
            payload: JSON-serializable payload or Pydantic model.
        """
        conn = await self.get(conn_id)
        if conn is None:
            return

        body: PayloadDict
        if isinstance(payload, BaseModel):
            body = payload.model_dump()
        else:
            body = payload

        message = {"event": event, "payload": body}
        try:
            await conn.raw_socket.send_json(message)
        except Exception:
            logger.error(
                "Unexpected send failure for connection %s",
                conn_id,
                exc_info=True,
            )

    def _make_emitter(
        self,
        conn: Connection,
    ) -> Callable[[EventName, PayloadDict | BaseModel], Awaitable[None]]:
        async def emit(
            event: EventName,
            payload: PayloadDict | BaseModel,
        ) -> None:
            await self.send(conn.id, event, payload)

        return emit

    def _make_disconnector(
        self,
        conn: Connection,
        full_lifecycle: Callable[[Connection, str], Awaitable[None]] | None = None,
    ) -> Callable[[str], Awaitable[None]]:
        """Return a bound disconnect callable for this connection.

        Args:
            conn: The connection to disconnect.
            full_lifecycle: If provided, called instead of the bare
                ``disconnect`` so that rooms, sessions, hooks, and router
                queues are all cleaned up on server-initiated disconnects.
        """

        async def disconnect(reason: str = "server_close") -> None:
            logger.info("Disconnecting connection %s: %s", conn.id, reason)
            try:
                await conn.raw_socket.close()
            except Exception:  # noqa: BLE001
                pass
            if full_lifecycle is not None:
                await full_lifecycle(conn, reason)
            else:
                await self.disconnect(conn)

        return disconnect
