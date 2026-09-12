# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for SessionManager — config, touch, heartbeat, and expiry warnings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from socketspec.connection import Connection, Identity, SessionInfo
from socketspec.session import SessionConfig, SessionManager
from socketspec.testing import TestRawSocket


@pytest.fixture
def session_config() -> SessionConfig:
    return SessionConfig(
        max_duration=3600,
        idle_timeout=300,
        heartbeat_interval=25,
        heartbeat_timeout=10,
        token_refresh_window=60,
    )


@pytest.fixture
def session_manager(session_config: SessionConfig) -> SessionManager:
    return SessionManager(session_config)


def test_session_config_defaults_are_sensible() -> None:
    config = SessionConfig()
    assert config.max_duration == 7200
    assert config.idle_timeout == 300
    assert config.heartbeat_interval == 25
    assert config.heartbeat_timeout == 10
    assert config.token_refresh_window == 60


def test_session_config_zero_max_duration_means_no_limit() -> None:
    config = SessionConfig(max_duration=0)
    assert config.max_duration == 0


async def test_start_creates_heartbeat_task(session_manager: SessionManager) -> None:
    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c1",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    # mock emit/disconnect
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    await session_manager.start(conn)
    assert conn.id in session_manager._tasks
    assert conn.id in session_manager._pong_events
    await session_manager.stop(conn.id)


async def test_stop_cancels_heartbeat_task(session_manager: SessionManager) -> None:
    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c2",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    await session_manager.start(conn)
    task = session_manager._tasks[conn.id]
    await session_manager.stop(conn.id)
    assert conn.id not in session_manager._tasks
    assert conn.id not in session_manager._pong_events
    assert task.cancelled()


async def test_stop_cleans_up_auth_expiry_warned_set(
    session_manager: SessionManager,
) -> None:
    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c3",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    await session_manager.start(conn)
    session_manager._auth_expiry_warned.add(conn.id)
    await session_manager.stop(conn.id)
    assert conn.id not in session_manager._auth_expiry_warned


async def test_stop_nonexistent_conn_does_not_raise(
    session_manager: SessionManager,
) -> None:
    await session_manager.stop("no-such-id")


async def test_touch_updates_last_active(session_manager: SessionManager) -> None:
    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c4",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now - timedelta(seconds=10),
    )
    prev = conn.last_active
    await session_manager.touch(conn)
    assert conn.last_active > prev


async def test_signal_pong_sets_pong_event(session_manager: SessionManager) -> None:
    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c5",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    await session_manager.start(conn)
    event = session_manager._pong_events[conn.id]
    assert not event.is_set()
    session_manager.signal_pong(conn.id)
    assert event.is_set()
    await session_manager.stop(conn.id)


async def test_signal_pong_nonexistent_conn_does_not_raise(
    session_manager: SessionManager,
) -> None:
    session_manager.signal_pong("ghost-id")


async def test_auth_expiry_warning_emitted_once_only(
    session_manager: SessionManager,
) -> None:
    now = datetime.now(timezone.utc)
    token_expiry = now + timedelta(seconds=30)  # within 60s warning window
    conn = Connection(
        id="c6",
        raw_socket=TestRawSocket(),
        identity=Identity(token_expires_at=token_expiry),
        session=SessionInfo(
            started_at=now, expires_at=None, token_expires_at=token_expiry
        ),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    await session_manager._check_token_expiry(conn)
    conn._emit_fn.assert_called_once()
    assert conn.id in session_manager._auth_expiry_warned

    # reset and check again
    conn._emit_fn.reset_mock()
    await session_manager._check_token_expiry(conn)
    # should not emit again since already warned
    conn._emit_fn.assert_not_called()


async def test_auth_expiry_not_emitted_when_no_token_expiry(
    session_manager: SessionManager,
) -> None:
    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c7",
        raw_socket=TestRawSocket(),
        identity=Identity(token_expires_at=None),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    await session_manager._check_token_expiry(conn)
    conn._emit_fn.assert_not_called()


async def test_auth_expiry_not_emitted_when_expiry_is_far_future(
    session_manager: SessionManager,
) -> None:
    now = datetime.now(timezone.utc)
    token_expiry = now + timedelta(hours=10)
    conn = Connection(
        id="c8",
        raw_socket=TestRawSocket(),
        identity=Identity(token_expires_at=token_expiry),
        session=SessionInfo(
            started_at=now, expires_at=None, token_expires_at=token_expiry
        ),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    await session_manager._check_token_expiry(conn)
    conn._emit_fn.assert_not_called()
