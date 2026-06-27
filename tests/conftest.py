# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from socketspec.backends.memory import MemoryBackend
from socketspec.connection import Connection, Identity, SessionInfo
from socketspec.testing import TestRawSocket


@pytest.fixture
def memory_backend() -> MemoryBackend:
    return MemoryBackend()


def make_connection(conn_id: str = "conn-1") -> Connection:
    now = datetime.now(timezone.utc)
    session = SessionInfo(started_at=now, expires_at=None, token_expires_at=None)
    return Connection(
        id=conn_id,
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=session,
        connected_at=now,
        last_active=now,
    )
