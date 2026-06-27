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

    @app.on_event("startup")
    async def startup() -> None:
        socket_app._startup_validate()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await socket_app._graceful_shutdown()

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
            return

        try:
            while True:
                data = await websocket.receive_text()
                await socket_app.handle_event(conn, data)
        except WebSocketDisconnect as exc:
            await socket_app.handle_disconnect(conn, reason=str(exc.code))
        except Exception:
            logger.error(
                "Unexpected WebSocket error for connection %s",
                conn.id,
                exc_info=True,
            )
            await socket_app.handle_disconnect(conn, reason="server_error")

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
