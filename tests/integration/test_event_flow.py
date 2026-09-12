# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Integration tests for SocketSpec — full connection/event flow using TestClient."""

from __future__ import annotations

import asyncio

import anyio
import pytest
from pydantic import BaseModel, Field

from socketspec.app import SocketApp
from socketspec.connection import Connection
from socketspec.security.ratelimit import RateLimit
from socketspec.testing import TestClient

# ── Setup Models ─────────────────────────────────────────────────────────────


class MessagePayload(BaseModel):
    text: str = Field(min_length=1)
    meta: str = "default"


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_connect_and_disconnect_lifecycle() -> None:
    app = SocketApp()
    connected_calls = 0
    disconnected_calls = 0

    @app.on_connect
    async def handle_connect(conn: Connection) -> None:
        nonlocal connected_calls
        connected_calls += 1

    @app.on_disconnect
    async def handle_disconnect(conn: Connection, reason: str) -> None:
        nonlocal disconnected_calls
        disconnected_calls += 1

    client = TestClient(app)
    async with client.connect():
        assert connected_calls == 1
        assert disconnected_calls == 0

    assert disconnected_calls == 1


@pytest.mark.anyio
async def test_emit_event_and_receive_response() -> None:
    app = SocketApp()

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {"status": "ok"})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        response = await conn.receive("pong")
        assert response["status"] == "ok"


@pytest.mark.anyio
async def test_emit_event_with_valid_payload_succeeds() -> None:
    app = SocketApp()

    @app.on("message")
    async def on_message(conn: Connection, payload: MessagePayload) -> None:
        await conn.emit("ack", {"received": payload.text})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("message", {"text": "hello"})
        ack = await conn.receive("ack")
        assert ack["received"] == "hello"


@pytest.mark.anyio
async def test_emit_event_with_missing_required_field_returns_error() -> None:
    app = SocketApp()

    @app.on("message")
    async def on_message(conn: Connection, payload: MessagePayload) -> None:
        pass

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("message", {"meta": "val"})  # 'text' missing
        err = await conn.receive("__error__")
        assert err["code"] == "VALIDATION_ERROR"
        assert "text" in str(err["details"])


@pytest.mark.anyio
async def test_emit_event_with_wrong_type_returns_validation_error() -> None:
    app = SocketApp()

    @app.on("message")
    async def on_message(conn: Connection, payload: MessagePayload) -> None:
        pass

    client = TestClient(app)
    async with client.connect() as conn:
        # text should be string
        await conn.emit("message", {"text": 12345})
        err = await conn.receive("__error__")
        assert err["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_emit_unknown_event_returns_unknown_event_error() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ghost_event", {})
        err = await conn.receive("__error__")
        assert err["code"] == "UNKNOWN_EVENT"


@pytest.mark.anyio
async def test_pong_keeps_connection_alive() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("__pong__", {})
        # Should not raise any error, connection remains active
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_payload_too_large_returns_error() -> None:
    app = SocketApp(max_payload_size=20)
    client = TestClient(app)
    async with client.connect() as conn:
        huge_payload = {"text": "x" * 100}
        import json

        await app.handle_event(
            conn.connection, json.dumps({"event": "message", "payload": huge_payload})
        )
        err = await conn.receive("__error__")
        assert err["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.anyio
async def test_invalid_json_returns_validation_error() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        await app.handle_event(conn.connection, "not-json-at-all")
        err = await conn.receive("__error__")
        assert err["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_on_connect_hook_fires_on_connect() -> None:
    app = SocketApp()
    fired = False

    @app.on_connect
    async def hook(conn: Connection) -> None:
        nonlocal fired
        fired = True

    client = TestClient(app)
    async with client.connect():
        pass
    assert fired is True


@pytest.mark.anyio
async def test_on_disconnect_hook_fires_on_disconnect() -> None:
    app = SocketApp()
    fired = False

    @app.on_disconnect
    async def hook(conn: Connection, reason: str) -> None:
        nonlocal fired
        fired = True

    client = TestClient(app)
    async with client.connect():
        pass
    assert fired is True


@pytest.mark.anyio
async def test_on_error_hook_fires_on_handler_exception() -> None:
    app = SocketApp()
    error_received = None

    @app.on("fail")
    async def fail(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("crashed")

    @app.on_error
    async def error_hook(conn: Connection, exc: Exception) -> None:
        nonlocal error_received
        error_received = exc

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("fail", {})
        # Wait for unordered handler task to run
        await anyio.sleep(0.05)
        assert isinstance(error_received, ValueError)
        assert str(error_received) == "crashed"


@pytest.mark.anyio
async def test_middleware_runs_before_handler() -> None:
    app = SocketApp()
    flow: list[str] = []

    @app.middleware
    async def mid(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        flow.append("mid")
        await call_next()

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        flow.append("handler")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        await anyio.sleep(0.05)
        assert flow == ["mid", "handler"]


@pytest.mark.anyio
async def test_middleware_abort_prevents_handler_execution() -> None:
    app = SocketApp()
    flow: list[str] = []

    @app.middleware
    async def block(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        flow.append("blocked")

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        flow.append("handler")

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        await anyio.sleep(0.05)
        assert flow == ["blocked"]


@pytest.mark.anyio
async def test_rate_limit_blocks_after_limit_exceeded() -> None:
    app = SocketApp(rate_limit=RateLimit(events=2, per_seconds=10))

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        await conn.receive("pong")
        await conn.emit("ping", {})
        await conn.receive("pong")

        # Exceeds limit
        await conn.emit("ping", {})
        err = await conn.receive("__error__")
        assert err["code"] == "RATE_LIMIT_ERROR"


@pytest.mark.anyio
async def test_rate_limit_does_not_block_different_connections() -> None:
    app = SocketApp(rate_limit=RateLimit(events=1, per_seconds=10))

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {})

    client = TestClient(app)
    async with client.connect() as c1, client.connect() as c2:
        await c1.emit("ping", {})
        await c1.receive("pong")

        await c2.emit("ping", {})
        await c2.receive("pong")


@pytest.mark.anyio
async def test_multiple_events_processed_correctly() -> None:
    app = SocketApp()

    @app.on("e1")
    async def e1(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("r1", {})

    @app.on("e2")
    async def e2(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("r2", {})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("e1", {})
        await conn.receive("r1")
        await conn.emit("e2", {})
        await conn.receive("r2")


@pytest.mark.anyio
async def test_handler_exception_does_not_close_connection() -> None:
    app = SocketApp()

    @app.on("crash")
    async def crash(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("crashed")

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("crash", {})
        await conn.receive("__error__")

        await conn.emit("ping", {})
        await conn.receive("pong")
        assert not conn.connection.raw_socket.closed


@pytest.mark.anyio
async def test_ordered_events_arrive_in_sequence() -> None:
    app = SocketApp()
    seq: list[int] = []

    @app.on("step", ordered=True)
    async def step(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        val = payload["val"]
        await asyncio.sleep(0.05 if val == 1 else 0.01)
        seq.append(val)

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("step", {"val": 1})
        await conn.emit("step", {"val": 2})
        await anyio.sleep(0.1)
        assert seq == [1, 2]


@pytest.mark.anyio
async def test_auth_required_rejects_unauthenticated_connection() -> None:
    from socketspec.security.auth import APIKeyAuth

    app = SocketApp(auth=APIKeyAuth(api_key="valid-key"))
    client = TestClient(app)  # no key
    with pytest.raises(RuntimeError, match="rejected"):
        async with client.connect():
            pass


@pytest.mark.anyio
async def test_auth_required_accepts_valid_token() -> None:
    from socketspec.security.auth import APIKeyAuth

    app = SocketApp(auth=APIKeyAuth(api_key="valid-key"))
    client = TestClient(app)
    async with client.connect(query_params={"api_key": "valid-key"}) as conn:
        assert conn.connection.identity is not None


@pytest.mark.anyio
async def test_origin_check_rejects_disallowed_origin() -> None:
    app = SocketApp(allowed_origins=["http://localhost"])
    # TestClient headers origin is http://testserver
    client = TestClient(app)
    with pytest.raises(RuntimeError, match="rejected"):
        async with client.connect():
            pass


@pytest.mark.anyio
async def test_origin_check_accepts_allowed_origin() -> None:
    app = SocketApp(allowed_origins=["http://testserver"])
    client = TestClient(app)
    async with client.connect():
        pass


@pytest.mark.anyio
async def test_connection_metadata_persists_across_events() -> None:
    app = SocketApp()

    @app.on("set")
    async def set_val(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        conn.metadata["shared"] = "value123"

    @app.on("get")
    async def get_val(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("result", {"val": conn.metadata.get("shared")})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("set", {})
        await anyio.sleep(0.02)
        await conn.emit("get", {})
        res = await conn.receive("result")
        assert res["val"] == "value123"
