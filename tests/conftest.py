# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Shared fixtures for the SocketSpec test suite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from socketspec.backends.memory import MemoryBackend
from socketspec.connection import Connection, Identity, SessionInfo
from socketspec.manager import ConnectionManager
from socketspec.registry import EventRegistry
from socketspec.rooms import RoomManager
from socketspec.session import SessionConfig, SessionManager
from socketspec.testing import TestRawSocket


def make_connection(
    conn_id: str = "conn-1",
    user_id: str | None = None,
    namespace: str = "/",
) -> Connection:
    """Build a bare Connection with a TestRawSocket."""
    now = datetime.now(timezone.utc)
    return Connection(
        id=conn_id,
        raw_socket=TestRawSocket(),
        identity=Identity(user_id=user_id),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
        namespace=namespace,
    )


@pytest.fixture
def memory_backend() -> MemoryBackend:
    return MemoryBackend()


@pytest.fixture
def registry() -> EventRegistry:
    return EventRegistry()


@pytest.fixture
def backend() -> MemoryBackend:
    return MemoryBackend()


@pytest.fixture
def manager(backend: MemoryBackend) -> ConnectionManager:
    return ConnectionManager(backend)


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


@pytest.fixture
def room_manager(backend: MemoryBackend, manager: ConnectionManager) -> RoomManager:
    return RoomManager(backend, manager)


class SimplePayload(BaseModel):
    text: str
    count: int = 0


class StrictPayload(BaseModel):
    required_field: str
    optional_field: str = "default"
