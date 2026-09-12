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

"""FastAPI adapter mounting SocketSpec WebSocket and docs routes.

Owns translation between FastAPI WebSocket and SocketSpec Connection.
Does NOT own business logic or event handlers.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from socketspec.app import SocketApp
from socketspec.docs.router import mount_docs

logger = logging.getLogger(__name__)

ORIGIN_REJECT_CLOSE_CODE = 1008
DEFAULT_WS_PATH = "/ws"


def mount(
    socket_app: SocketApp,
    app: FastAPI,
    *,
    path: str = DEFAULT_WS_PATH,
) -> None:
    """Mount a SocketApp into a FastAPI application.

    Args:
        socket_app: Configured SocketSpec application.
        app: FastAPI application to mount onto.
        path: WebSocket endpoint path.
    """

    from contextlib import asynccontextmanager  # noqa: PLC0415

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def socketspec_lifespan(app: FastAPI) -> AsyncIterator[None]:
        socket_app._startup_validate()
        # F-04: try/finally ensures _graceful_shutdown() is called even if the
        # application crashes (an exception propagating through yield would
        # otherwise skip the shutdown call entirely).
        try:
            if original_lifespan:
                async with original_lifespan(app):
                    yield
            else:
                yield
        finally:
            await socket_app._graceful_shutdown()

    app.router.lifespan_context = socketspec_lifespan

    @app.websocket(path)
    async def websocket_endpoint(websocket: WebSocket) -> None:
        headers = dict(websocket.headers)
        query_params = dict(websocket.query_params)
        origin = headers.get("origin")
        if not socket_app._origin_validator.is_allowed(origin):
            await websocket.close(code=ORIGIN_REJECT_CLOSE_CODE)
            return

        await websocket.accept()

        conn = await socket_app.handle_connect(
            raw_socket=FastAPISocketWrapper(websocket),
            headers=headers,
            query_params=query_params,
        )
        if conn is None:
            # F-05: if handle_connect didn't already close the socket (e.g.
            # the auth backend closed it with its own code via FastAPISocketWrapper),
            # send an explicit Policy Violation close so the client always gets
            # a meaningful signal. Check application_state to avoid double-close.
            from starlette.websockets import WebSocketState  # noqa: PLC0415

            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.close(code=1008)
            return

        # F-03: isolate the receive() call from handle_event() so that a
        # transient error in event processing never tears down the connection.
        # Only a true WebSocket-level disconnect (WebSocketDisconnect) or an
        # unrecoverable exception from receive_text() itself ends the loop.
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect as exc:
                await socket_app.handle_disconnect(conn, reason=str(exc.code))
                return
            except Exception:
                logger.error(
                    "Unrecoverable WebSocket receive error for connection %s",
                    conn.id,
                    exc_info=True,
                )
                await socket_app.handle_disconnect(conn, reason="server_error")
                return
            try:
                await socket_app.handle_event(conn, data)
            except Exception:
                # handle_event already emits an __error__ envelope to the
                # client; log here for server-side observability and continue.
                logger.error(
                    "Unexpected error processing event for connection %s",
                    conn.id,
                    exc_info=True,
                )

    if socket_app._docs:
        mount_docs(app, socket_app)

    if socket_app._debug:
        from socketspec.docs.debug_router import mount_debug  # noqa: PLC0415

        mount_debug(app, socket_app)


class FastAPISocketWrapper:
    """Normalizes FastAPI WebSocket to the RawSocket interface."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON message frame to the client."""
        await self._ws.send_json(data)

    async def close(self, code: int = 1000) -> None:
        """Close the underlying WebSocket."""
        await self._ws.close(code=code)
