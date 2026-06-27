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

"""Session configuration and per-connection TTL enforcement.

Owns heartbeat, idle timeout, and max-duration tasks per connection.
Does NOT own connection state or authentication refresh logic.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from socketspec.connection import Connection
from socketspec.types import ConnectionId

logger = logging.getLogger(__name__)

DEFAULT_MAX_DURATION_SECONDS = 7200
DEFAULT_IDLE_TIMEOUT_SECONDS = 300
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 25
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 10
DEFAULT_TOKEN_REFRESH_WINDOW_SECONDS = 60
DEFAULT_REDIS_KEY_TTL_SECONDS = 7200


@dataclass
class SessionConfig:
    """TTL and heartbeat settings for WebSocket sessions."""

    max_duration: int = DEFAULT_MAX_DURATION_SECONDS
    idle_timeout: int = DEFAULT_IDLE_TIMEOUT_SECONDS
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS
    token_refresh_window: int = DEFAULT_TOKEN_REFRESH_WINDOW_SECONDS
    redis_key_ttl: int = DEFAULT_REDIS_KEY_TTL_SECONDS


class SessionManager:
    """Manages heartbeat tasks and TTL enforcement per connection.

    Note:
        One background task runs per connection from connect until disconnect.
    """

    def __init__(self, config: SessionConfig) -> None:
        self._config = config
        self._tasks: dict[ConnectionId, asyncio.Task[None]] = {}
        self._pong_events: dict[ConnectionId, asyncio.Event] = {}
        self._auth_expiry_warned: set[ConnectionId] = set()

    async def start(self, conn: Connection) -> None:
        """Start heartbeat and TTL monitoring for a connection.

        Args:
            conn: The connection to monitor.
        """
        self._pong_events[conn.id] = asyncio.Event()
        task = asyncio.create_task(self._session_loop(conn))
        self._tasks[conn.id] = task

    async def stop(self, conn_id: ConnectionId) -> None:
        """Cancel all session tasks for a connection on disconnect.

        Args:
            conn_id: The connection id whose tasks should be cancelled.
        """
        task = self._tasks.pop(conn_id, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._pong_events.pop(conn_id, None)
        self._auth_expiry_warned.discard(conn_id)

    async def touch(self, conn: Connection) -> None:
        """Update last_active on every incoming event.

        Args:
            conn: The connection that received an event.
        """
        conn.last_active = datetime.now(timezone.utc)

    def signal_pong(self, conn_id: ConnectionId) -> None:
        """Signal that a __pong__ frame was received for a connection.

        Args:
            conn_id: The connection that sent the pong.
        """
        event = self._pong_events.get(conn_id)
        if event is not None:
            event.set()

    async def _session_loop(self, conn: Connection) -> None:
        """Run heartbeat pings and enforce idle and max-duration limits."""
        try:
            while True:
                await asyncio.sleep(self._config.heartbeat_interval)
                await self._check_timeouts(conn)
                await self._check_token_expiry(conn)

                # Send ping, then immediately clear the pong event so that any
                # pong arriving during the next sleep window is not silently
                # consumed before we start waiting for it.
                await conn.emit("__ping__", {})
                pong_event = self._pong_events.get(conn.id)
                if pong_event is not None:
                    pong_event.clear()
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(pong_event.wait()),
                            timeout=self._config.heartbeat_timeout,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Connection %s did not respond to __ping__ within %ss — "
                            "disconnecting as dead",
                            conn.id,
                            self._config.heartbeat_timeout,
                        )
                        await conn.disconnect("heartbeat_timeout")
                        return
        except asyncio.CancelledError:
            raise

    async def _check_timeouts(self, conn: Connection) -> None:
        now = datetime.now(timezone.utc)
        if self._config.max_duration > 0:
            max_end = conn.session.started_at + timedelta(
                seconds=self._config.max_duration
            )
            if now >= max_end:
                logger.info("Connection %s reached max session duration", conn.id)
                await conn.emit(
                    "__session_expiring__",
                    {"reason": "max_duration"},
                )
                await conn.disconnect("max_duration")
                return

        if self._config.idle_timeout > 0:
            idle_limit = conn.last_active + timedelta(
                seconds=self._config.idle_timeout
            )
            if now >= idle_limit:
                logger.info("Connection %s idle timeout exceeded", conn.id)
                await conn.emit(
                    "__idle_warning__",
                    {"reason": "idle_timeout"},
                )
                await conn.disconnect("idle_timeout")

    async def _check_token_expiry(self, conn: Connection) -> None:
        token_expires_at = conn.identity.token_expires_at
        if token_expires_at is None:
            return
        now = datetime.now(timezone.utc)
        warning_at = token_expires_at - timedelta(
            seconds=self._config.token_refresh_window
        )
        if now >= warning_at:
            if conn.id in self._auth_expiry_warned:
                return
            await conn.emit(
                "__auth_expiring__",
                {"expires_at": token_expires_at.isoformat()},
            )
            self._auth_expiry_warned.add(conn.id)
