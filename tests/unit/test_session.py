# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from socketspec.session import SessionConfig, SessionManager
from tests.conftest import make_connection


async def test_touch_updates_last_active_timestamp() -> None:
    manager = SessionManager(SessionConfig())
    conn = make_connection("c1")
    original = conn.last_active
    await manager.touch(conn)
    assert conn.last_active >= original


async def test_start_and_stop_session_tasks() -> None:
    manager = SessionManager(SessionConfig(heartbeat_interval=60))
    conn = make_connection("c1")
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()
    await manager.start(conn)
    assert conn.id in manager._tasks
    await manager.stop(conn.id)
    assert conn.id not in manager._tasks


async def test_session_loop_emits_ping() -> None:
    manager = SessionManager(SessionConfig(heartbeat_interval=0))
    conn = make_connection("c1")
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()
    await manager.start(conn)
    await asyncio.sleep(0.01)
    await manager.stop(conn.id)
    conn._emit_fn.assert_called()
