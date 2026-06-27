# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import anyio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from socketspec.app import SocketApp
from socketspec.connection import Connection
from socketspec.di import Depends
from socketspec.rooms import Room
from socketspec.session import SessionConfig, SessionManager
from socketspec.testing import TestClient
from tests.conftest import make_connection


class HookPayload(BaseModel):
    value: str


async def test_on_connect_hook_runs_after_connection() -> None:
    app = SocketApp()
    seen: list[str] = []

    @app.on_connect
    async def on_connect(conn: Connection) -> None:
        seen.append(conn.id)

    async with TestClient(app).connect() as conn:
        assert seen == [conn.connection.id]


async def test_on_disconnect_hook_runs_on_teardown() -> None:
    app = SocketApp()
    seen: list[str] = []

    @app.on_disconnect
    async def on_disconnect(conn: Connection, reason: str) -> None:
        seen.append(reason)

    async with TestClient(app).connect():
        pass

    assert seen == ["test_close"]


async def test_room_join_and_leave_hooks_run() -> None:
    app = SocketApp()
    joins: list[str] = []
    leaves: list[str] = []

    @app.on("enter")
    async def enter(conn: Connection, payload: dict[str, object]) -> None:
        await app.rooms.join(conn, "hook-room")

    @app.on_room_join
    async def on_join(conn: Connection, room: str) -> None:
        joins.append(room)

    @app.on_room_leave
    async def on_leave(conn: Connection, room: str) -> None:
        leaves.append(room)

    async with TestClient(app).connect() as conn:
        await conn.emit("enter", {})
        await anyio.sleep(0.05)

    assert joins == ["hook-room"]
    assert leaves == ["hook-room"]


async def test_payload_too_large_emits_error() -> None:
    app = SocketApp(max_payload_size=10)
    async with TestClient(app).connect() as conn:
        await app.handle_event(conn.connection, "x" * 20)
        error = await conn.receive("__error__")
        assert error["code"] == "PAYLOAD_TOO_LARGE"


async def test_invalid_json_emits_validation_error() -> None:
    app = SocketApp()
    async with TestClient(app).connect() as conn:
        await app.handle_event(conn.connection, "not-json")
        error = await conn.receive("__error__")
        assert error["code"] == "VALIDATION_ERROR"


async def test_static_room_registered_at_startup() -> None:
    app = SocketApp(rooms=[Room(name="lobby")])
    assert "lobby" in app.rooms._static_rooms


async def test_room_guard_decorator_registers_guard() -> None:
    app = SocketApp()

    @app.room_guard("team:{team_id}")
    async def team_guard(conn: Connection, team_id: str) -> bool:
        return team_id == "alpha"

    assert len(app.rooms._guards) == 1


async def test_middleware_decorator_registers_middleware() -> None:
    app = SocketApp()
    called = False

    @app.middleware
    async def track(
        conn: Connection,
        event: str,
        payload: dict[str, object],
        nxt: object,
    ) -> None:
        nonlocal called
        called = True
        await nxt()

    @app.on("ping")
    async def ping(conn: Connection, payload: dict[str, object]) -> None:
        await conn.emit("pong", {})

    async with TestClient(app).connect() as conn:
        await conn.emit("ping", {})
        await anyio.sleep(0.05)
        assert called is True


async def test_depends_works_in_handler() -> None:
    app = SocketApp()

    async def provide_tag() -> str:
        return "tagged"

    @app.on("tagged")
    async def tagged(
        conn: Connection,
        payload: dict[str, object],
        tag: str = Depends(provide_tag),
    ) -> None:
        await conn.emit("tag", {"tag": tag})

    async with TestClient(app).connect() as conn:
        await conn.emit("tagged", {})
        await anyio.sleep(0.05)
        response = await conn.receive("tag")
        assert response["tag"] == "tagged"


async def test_test_connection_join_room_helper() -> None:
    app = SocketApp()
    async with TestClient(app).connect() as conn:
        await conn.join_room("helpers")
        assert "helpers" in conn.connection.rooms


async def test_session_max_duration_disconnects_connection() -> None:
    manager = SessionManager(SessionConfig(max_duration=1, heartbeat_interval=3600))
    conn = make_connection("c1")
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()
    conn.session.started_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    await manager._check_timeouts(conn)
    conn._disconnect_fn.assert_called_once()


async def test_docs_static_assets_served_with_bearer_token() -> None:
    from socketspec.adapters.fastapi import mount

    socket_app = SocketApp(docs=True, docs_access_token="secret-token")
    app = FastAPI()
    mount(socket_app, app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        js = await client.get(
            "/socket-docs/main.js",
            headers={"Authorization": "Bearer secret-token"},
        )
        css = await client.get(
            "/socket-docs/style.css",
            headers={"Authorization": "Bearer secret-token"},
        )
        assert js.status_code == 200
        assert css.status_code == 200


async def test_graceful_shutdown_closes_backend() -> None:
    app = SocketApp()
    await app._graceful_shutdown()
