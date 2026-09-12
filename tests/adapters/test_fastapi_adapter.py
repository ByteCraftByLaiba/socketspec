# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for SocketSpec FastAPI Adapter — WebSocket endpoints, docs, and validation."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from starlette.testclient import TestClient as StarletteTestClient

from socketspec.adapters.fastapi import mount
from socketspec.app import SocketApp


class EchoPayload(BaseModel):
    text: str


def test_mount_registers_websocket_endpoint() -> None:
    socket_app = SocketApp()
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/ws" in routes


def test_mount_registers_docs_routes_when_docs_enabled() -> None:
    socket_app = SocketApp(docs=True)
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/socket-docs" in routes
    assert "/socket-docs/schema" in routes


def test_mount_does_not_register_docs_routes_when_docs_disabled() -> None:
    socket_app = SocketApp(docs=False)
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/socket-docs" not in routes


def test_mount_registers_debug_routes_when_debug_enabled() -> None:
    socket_app = SocketApp(debug=True)
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/socket-debug" in routes
    assert "/socket-debug/stream" in routes


def test_websocket_connect_and_send_event() -> None:
    socket_app = SocketApp()

    @socket_app.on("echo")
    async def handle_echo(conn: object, payload: EchoPayload) -> None:
        await conn.emit("echoed", payload.model_dump())  # type: ignore[attr-defined]

    app = FastAPI()
    mount(socket_app, app, path="/ws")
    socket_app._startup_validate()

    with StarletteTestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://test"}) as ws:
            ws.send_json({"event": "echo", "payload": {"text": "hello"}})
            message = ws.receive_json()
            assert message["event"] == "echoed"
            assert message["payload"]["text"] == "hello"


def test_websocket_disconnect_triggers_cleanup() -> None:
    socket_app = SocketApp()
    disconnected = False

    @socket_app.on_disconnect
    async def hook(conn: object, reason: str) -> None:
        nonlocal disconnected
        disconnected = True

    app = FastAPI()
    mount(socket_app, app, path="/ws")
    socket_app._startup_validate()

    with StarletteTestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://test"}):
            pass
    assert disconnected is True


@pytest.mark.anyio
async def test_docs_schema_endpoint_returns_valid_json() -> None:
    socket_app = SocketApp(docs=True)
    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/socket-docs/schema")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "events" in data


@pytest.mark.anyio
async def test_docs_index_returns_html() -> None:
    socket_app = SocketApp(docs=True)
    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/socket-docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_docs_schema_contains_registered_events() -> None:
    socket_app = SocketApp(docs=True)

    @socket_app.on("ping", description="Ping event")
    async def handle_ping(conn: object, payload: dict[str, object]) -> None:
        pass

    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/socket-docs/schema")
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "ping"
        assert data["events"][0]["description"] == "Ping event"


def test_startup_validation_runs_on_app_startup() -> None:
    socket_app = SocketApp()
    app = FastAPI()
    mount(socket_app, app)

    # FastAPI triggers startup events when using TestClient context
    with StarletteTestClient(app):
        # Once startup runs, compiled chain should not be
        # router.dispatch directly anymore — compiled with middleware.
        assert socket_app._compiled_chain is not socket_app._router.dispatch


def test_duplicate_event_raises_at_startup() -> None:
    from socketspec.errors import DuplicateEventError

    socket_app = SocketApp()

    @socket_app.on("dup")
    async def h1(conn: object, payload: dict) -> None:  # type: ignore[type-arg]
        pass

    # Registering the same name again via the decorator must raise immediately
    with pytest.raises(DuplicateEventError):

        @socket_app.on("dup")
        async def h2(conn: object, payload: dict) -> None:  # type: ignore[type-arg]
            pass
