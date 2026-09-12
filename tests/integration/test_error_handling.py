# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Integration tests for SocketSpec error handling and error envelope formats."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field

from socketspec.app import SocketApp
from socketspec.connection import Connection
from socketspec.security.ratelimit import RateLimit
from socketspec.testing import TestClient


class DummyModel(BaseModel):
    required_val: str = Field(min_length=2)


@pytest.mark.anyio
async def test_validation_error_envelope_shape() -> None:
    app = SocketApp()

    @app.on("test")
    async def handle(conn: Connection, payload: DummyModel) -> None:
        pass

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("test", {"required_val": "x"})  # too short
        err = await conn.receive("__error__")
        assert "request_id" in err
        assert err["code"] == "VALIDATION_ERROR"
        assert err["event"] == "test"
        assert "message" in err
        assert "details" in err
        assert "errors" in err["details"]


@pytest.mark.anyio
async def test_unknown_event_envelope_shape() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("nonexistent", {})
        err = await conn.receive("__error__")
        assert "request_id" in err
        assert err["code"] == "UNKNOWN_EVENT"
        assert err["event"] == "nonexistent"
        assert "message" in err


@pytest.mark.anyio
async def test_handler_error_envelope_shape() -> None:
    app = SocketApp()

    @app.on("fail")
    async def fail(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("crashed")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("fail", {})
        err = await conn.receive("__error__")
        assert "request_id" in err
        assert err["code"] == "HANDLER_ERROR"
        assert err["event"] == "fail"
        assert "crashed" in err["message"]


@pytest.mark.anyio
async def test_rate_limit_error_envelope_shape() -> None:
    # Rate-limit errors are minimal: only {"code": "RATE_LIMIT_ERROR"}
    app = SocketApp(rate_limit=RateLimit(events=1, per_seconds=10))

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        await conn.receive("pong")
        await conn.emit("ping", {})
        err = await conn.receive("__error__")
        assert err["code"] == "RATE_LIMIT_ERROR"


@pytest.mark.anyio
async def test_payload_too_large_envelope_shape() -> None:
    # Payload-too-large errors are minimal: only {"code": "PAYLOAD_TOO_LARGE"}
    app = SocketApp(max_payload_size=10)
    client = TestClient(app)
    async with client.connect() as conn:
        await app.handle_event(
            conn.connection,
            json.dumps({"event": "ping", "payload": "x" * 20}),
        )
        err = await conn.receive("__error__")
        assert err["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.anyio
async def test_permission_error_does_not_close_connection() -> None:
    app = SocketApp()

    @app.room_guard("secret")
    async def guard(conn: Connection) -> bool:
        return False

    client = TestClient(app)
    async with client.connect() as conn:
        with pytest.raises(Exception):  # RoomPermissionError raised directly
            await app.rooms.join(conn.connection, "secret")
        # connection remains open
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_all_error_envelopes_have_request_id() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ghost", {})
        err = await conn.receive("__error__")
        assert "request_id" in err


@pytest.mark.anyio
async def test_all_error_envelopes_have_code() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ghost", {})
        err = await conn.receive("__error__")
        assert "code" in err


@pytest.mark.anyio
async def test_all_error_envelopes_have_event_name() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ghost", {})
        err = await conn.receive("__error__")
        assert err["event"] == "ghost"


@pytest.mark.anyio
async def test_all_error_envelopes_have_message() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ghost", {})
        err = await conn.receive("__error__")
        assert "message" in err


@pytest.mark.anyio
async def test_validation_error_includes_field_details() -> None:
    app = SocketApp()

    @app.on("test")
    async def handle(conn: Connection, payload: DummyModel) -> None:
        pass

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("test", {})  # missing required_val
        err = await conn.receive("__error__")
        assert err["code"] == "VALIDATION_ERROR"
        assert "details" in err
        assert "required_val" in str(err["details"])


@pytest.mark.anyio
async def test_connection_stays_open_after_validation_error() -> None:
    app = SocketApp()

    @app.on("test")
    async def handle(conn: Connection, payload: DummyModel) -> None:
        pass

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("test", {})
        await conn.receive("__error__")
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_connection_stays_open_after_handler_error() -> None:
    app = SocketApp()

    @app.on("fail")
    async def fail(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("crashed")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("fail", {})
        await conn.receive("__error__")
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_connection_stays_open_after_rate_limit_error() -> None:
    app = SocketApp(rate_limit=RateLimit(events=1, per_seconds=10))

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        await conn.receive("pong")
        await conn.emit("ping", {})
        await conn.receive("__error__")
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_connection_stays_open_after_unknown_event() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("unknown", {})
        await conn.receive("__error__")
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_auth_error_closes_connection() -> None:
    from socketspec.security.auth import APIKeyAuth

    app = SocketApp(auth=APIKeyAuth(api_key="secret"))
    client = TestClient(app)
    with pytest.raises(RuntimeError, match="rejected"):
        async with client.connect(query_params={"api_key": "wrong-key"}):
            pass
