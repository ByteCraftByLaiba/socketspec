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

"""In-process TestClient for automated SocketSpec tests without a live server.

Owns in-memory WebSocket simulation via asyncio queues.
Does NOT own production transport or framework adapters.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from socketspec.app import SocketApp
from socketspec.connection import Connection
from socketspec.types import EventName, PayloadDict, RoomName

logger = logging.getLogger(__name__)

DEFAULT_RECEIVE_TIMEOUT_SECONDS = 5.0


class TestRawSocket:
    """In-memory socket capturing outbound server messages."""

    def __init__(self) -> None:
        self.outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.closed = False
        self.close_code = 1000

    async def send_json(self, data: dict[str, Any]) -> None:
        if self.closed:
            return
        await self.outgoing.put(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code


class TestConnection:
    """Simulated client connection for in-process tests."""

    def __init__(
        self,
        app: SocketApp,
        conn: Connection,
        raw_socket: TestRawSocket,
    ) -> None:
        self._app = app
        self._conn = conn
        self._raw_socket = raw_socket

    @property
    def connection(self) -> Connection:
        """Underlying SocketSpec connection object."""
        return self._conn

    async def emit(self, event: EventName, payload: PayloadDict) -> None:
        """Send an event to the app as if the client sent it."""
        message = json.dumps({"event": event, "payload": payload})
        await self._app.handle_event(self._conn, message)

    async def receive(
        self,
        event: EventName,
        *,
        timeout: float = DEFAULT_RECEIVE_TIMEOUT_SECONDS,
    ) -> PayloadDict:
        """Wait for a specific outbound event from the server."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for event '{event}'")
            try:
                message = await asyncio.wait_for(
                    self._raw_socket.outgoing.get(),
                    timeout=remaining,
                )
            except TimeoutError as exc:
                raise TimeoutError(f"Timed out waiting for event '{event}'") from exc

            if message.get("event") == event:
                payload = message.get("payload", {})
                if isinstance(payload, dict):
                    return payload
                return {"value": payload}

    async def receive_broadcast(
        self,
        event: EventName,
        room: RoomName,
        *,
        timeout: float = DEFAULT_RECEIVE_TIMEOUT_SECONDS,
    ) -> PayloadDict:
        """Wait for a broadcast event (same wire format as receive)."""
        _ = room
        return await self.receive(event, timeout=timeout)

    async def join_room(self, room: RoomName) -> None:
        """Add this test connection to a room via RoomManager."""
        await self._app.rooms.join(self._conn, room)


class TestClient:
    """In-process WebSocket test client using memory queues."""

    def __init__(self, app: SocketApp, *, auth_token: str | None = None) -> None:
        self._app = app
        self._auth_token = auth_token
        self._started = False

    @asynccontextmanager
    async def connect(
        self,
        *,
        query_params: dict[str, str] | None = None,
    ) -> AsyncIterator[TestConnection]:
        """Open a simulated WebSocket connection through the full app stack."""
        if not self._started:
            self._app._startup_validate()
            self._started = True

        params = dict(query_params or {})
        if self._auth_token is not None:
            params.setdefault("token", self._auth_token)

        headers = {"origin": "http://testserver"}
        if self._auth_token is not None:
            headers["authorization"] = f"Bearer {self._auth_token}"

        raw_socket = TestRawSocket()
        conn = await self._app.handle_connect(
            raw_socket=raw_socket,
            headers=headers,
            query_params=params,
        )
        if conn is None:
            raise RuntimeError("TestClient connection was rejected by SocketApp")

        test_conn = TestConnection(self._app, conn, raw_socket)
        try:
            yield test_conn
        finally:
            await self._app.handle_disconnect(conn, reason="test_close")
