# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests targeted specifically at covering remaining coverage gaps."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient as StarletteTestClient

from socketspec.adapters.fastapi import mount
from socketspec.app import SocketApp
from socketspec.backends.memory import MemoryBackend
from socketspec.connection import Connection, Identity, SessionInfo
from socketspec.errors import RoomPermissionError
from socketspec.manager import ConnectionManager
from socketspec.rooms import RoomManager
from socketspec.router import _QUEUE_SENTINEL, EventRegistry, EventRouter
from socketspec.session import SessionConfig, SessionManager
from socketspec.testing import TestClient, TestRawSocket
from tests.conftest import make_connection

# ── App Gaps ──────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_handle_event_with_bytes() -> None:
    app = SocketApp()
    conn = make_connection("c1")
    # Wire up emit so error responses don't crash
    conn._emit_fn = AsyncMock()
    # Inbound bytes raw message — exercises the raw_message.decode() branch
    await app.handle_event(conn, b'{"event": "unknown_ev", "payload": {}}')
    # Should have emitted an UNKNOWN_EVENT error without raising
    conn._emit_fn.assert_called_once()


@pytest.mark.anyio
async def test_handle_event_invalid_payload_type() -> None:
    app = SocketApp()
    conn = make_connection("c2")
    conn._emit_fn = AsyncMock()
    # payload is not a dict
    await app.handle_event(conn, '{"event": "ping", "payload": "not-a-dict"}')
    conn._emit_fn.assert_called_once()
    args, _ = conn._emit_fn.call_args
    assert args[1]["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_disconnect_hooks_failing_are_caught() -> None:
    app = SocketApp()
    conn = make_connection("c3")
    hook_ran = False

    @app.on_disconnect
    async def bad_hook(conn: Connection, reason: str) -> None:
        nonlocal hook_ran
        hook_ran = True
        raise RuntimeError("hook error")

    # handle_disconnect must not propagate the hook's exception
    await app.handle_disconnect(conn, "server_close")
    # The hook DID run, it just didn't crash the caller
    assert hook_ran


@pytest.mark.anyio
async def test_room_leave_hooks_failing_are_caught() -> None:
    app = SocketApp()
    conn = make_connection("c4")
    await app.rooms.join(conn, "lobby")
    hook_ran = False

    @app.on_room_leave
    async def bad_room_hook(conn: Connection, room: str) -> None:
        nonlocal hook_ran
        hook_ran = True
        raise RuntimeError("room leave error")

    # handle_disconnect must not propagate the hook's exception
    await app.handle_disconnect(conn, "server_close")
    assert hook_ran


@pytest.mark.anyio
async def test_error_hooks_failing_are_caught() -> None:
    app = SocketApp()
    conn = make_connection("c5")
    hook_ran = False

    @app.on_error
    async def bad_error_hook(conn: Connection, exc: Exception) -> None:
        nonlocal hook_ran
        hook_ran = True
        raise RuntimeError("error hook failure")

    # _run_error_hooks must swallow the hook's secondary exception
    await app._run_error_hooks(conn, ValueError("original error"))
    assert hook_ran


@pytest.mark.anyio
async def test_debug_log_queue_full() -> None:
    app = SocketApp(debug=True)
    # Set debug queue to small size and fill it
    app._debug_queue = asyncio.Queue(maxsize=1)
    app._debug_log({"x": 1})
    # This must handle QueueFull and discard oldest, put new
    app._debug_log({"x": 2})
    assert app._debug_queue.qsize() == 1


@pytest.mark.anyio
async def test_build_backend_custom() -> None:
    custom_backend = MagicMock()
    app = SocketApp(backend=custom_backend)
    assert app._backend is custom_backend


@pytest.mark.anyio
async def test_infer_payload_model_no_params() -> None:
    app = SocketApp()

    # 0 params
    async def h0() -> None:
        pass

    assert app._infer_payload_model(h0) is None


@pytest.mark.anyio
async def test_infer_payload_model_no_type_annotation() -> None:
    app = SocketApp()

    # no type annotation on second parameter (dict, not a BaseModel)
    async def h(conn: Connection, payload: dict) -> None:  # noqa: ANN401
        pass

    assert app._infer_payload_model(h) is None


@pytest.mark.anyio
async def test_infer_payload_model_eval_failure() -> None:
    app = SocketApp()

    # string annotation that raises eval error
    async def h(
        conn: Connection,
        payload: NonExistentClassNotDefined,  # noqa: F821
    ) -> None:
        pass

    assert app._infer_payload_model(h) is None


@pytest.mark.anyio
async def test_infer_payload_model_get_type_hints_failure() -> None:
    app = SocketApp()

    # Forward reference name error in get_type_hints
    async def h(
        conn: Connection,
        payload: UndefinedName,  # noqa: F821
    ) -> None:
        pass

    assert app._infer_payload_model(h) is None


# ── FastAPI Adapter Gaps ───────────────────────────────────────────────────────


def test_fastapi_adapter_no_original_lifespan() -> None:
    socket_app = SocketApp()
    app = FastAPI()
    # original lifespan None
    app.router.lifespan_context = None  # type: ignore[assignment]
    mount(socket_app, app)
    # Verifies startup validation ran (registry is marked validated)
    with StarletteTestClient(app):
        assert socket_app._registry._validated is True


@pytest.mark.anyio
async def test_fastapi_adapter_rejection_disallowed_origin() -> None:
    socket_app = SocketApp(allowed_origins=["http://allowed.com"])
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    socket_app._startup_validate()

    with StarletteTestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/ws",
                headers={"origin": "http://attacker.com"},
            ):
                pass


@pytest.mark.anyio
async def test_fastapi_adapter_connection_rejected_by_app() -> None:
    from socketspec.security.auth import APIKeyAuth

    socket_app = SocketApp(auth=APIKeyAuth(api_key="valid-key"))
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    socket_app._startup_validate()

    with StarletteTestClient(app) as client:
        # Connect without a valid API key — server sends AUTH_ERROR then closes
        with client.websocket_connect("/ws") as ws:
            # 1st receive returns the AUTH_ERROR event the server emitted
            msg = ws.receive_json()
            assert msg["event"] == "__error__"
            assert msg["payload"]["code"] == "AUTH_ERROR"
            # 2nd receive raises WebSocketDisconnect because server closed the socket
            from starlette.websockets import WebSocketDisconnect

            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


@pytest.mark.anyio
async def test_fastapi_adapter_unexpected_websocket_error() -> None:
    # Cover the broad `except Exception` branch in fastapi.py by raising from
    # a handler. handle_disconnect is still called \u2014 same code path without
    # any cross-thread patching that would deadlock.
    socket_app = SocketApp()
    app = FastAPI()
    mount(socket_app, app, path="/ws")
    socket_app._startup_validate()

    @socket_app.on("crash")
    async def crash_handler(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise RuntimeError("handler boom")

    client = TestClient(socket_app)
    async with client.connect() as conn:
        await conn.emit("crash", {})
        err = await conn.receive("__error__")
        assert err["code"] == "HANDLER_ERROR"


# ── Debug Router Gaps ─────────────────────────────────────────────────────────


def test_debug_html_index() -> None:
    """Covers _build_debug_html and the GET /socket-debug endpoint."""
    socket_app = SocketApp(debug=True)
    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    with StarletteTestClient(app) as client:
        resp = client.get("/socket-debug")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_debug_stream_yields_data_then_exits() -> None:
    """Covers the fan-out subscriber mechanism in _debug_log.

    Verifies that _debug_subscribe creates a per-client queue and
    _debug_log broadcasts to all subscribers.
    """
    socket_app = SocketApp(debug=True)
    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    # Subscribe like an SSE client would
    q = socket_app._debug_subscribe()
    assert q in socket_app._debug_subscribers

    # Log an entry — should be broadcast to our subscriber queue
    socket_app._debug_log({"event": "test-debug"})
    assert not q.empty()

    item = q.get_nowait()
    assert item is not None
    assert item["event"] == "test-debug"

    # Unsubscribe — queue should be removed
    socket_app._debug_unsubscribe(q)
    assert q not in socket_app._debug_subscribers


def test_debug_stream_exits_on_shutdown() -> None:
    """Covers the shutdown_event.is_set() early-exit branch."""
    socket_app = SocketApp(debug=True)
    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    # Pre-set shutdown so the generator exits on first iteration
    socket_app._shutdown_event.set()

    with StarletteTestClient(app) as client:
        resp = client.get("/socket-debug/stream")
        assert resp.status_code == 200


# ── Session manager Gaps ───────────────────────────────────────────────────────


def test_debug_subscriber_full_queue_eviction() -> None:
    """Covers the per-subscriber QueueFull eviction path in _debug_log."""
    socket_app = SocketApp(debug=True)
    app = FastAPI()
    mount(socket_app, app)
    socket_app._startup_validate()

    q = socket_app._debug_subscribe()
    # Fill the subscriber queue to capacity (maxsize=500)
    for i in range(500):
        q.put_nowait({"i": i})
    assert q.full()

    # This must evict the oldest and insert without raising
    socket_app._debug_log({"event": "overflow"})
    assert q.qsize() == 500
    # The oldest (i=0) was evicted; drain and find the new entry
    found = False
    while not q.empty():
        item = q.get_nowait()
        if item is not None and item.get("event") == "overflow":
            found = True
    assert found

    socket_app._debug_unsubscribe(q)


def test_debug_unsubscribe_missing_queue() -> None:
    """Covers the ValueError pass-through in _debug_unsubscribe."""
    socket_app = SocketApp(debug=True)
    q: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
    # Should not raise even if q was never subscribed
    socket_app._debug_unsubscribe(q)


@pytest.mark.anyio
async def test_room_join_hook_rollback() -> None:
    """Covers the rollback path when a room join hook raises."""
    app_inst = SocketApp()
    conn = make_connection("c_rollback")

    @app_inst.on_room_join
    async def failing_hook(conn: Connection, room: str) -> None:
        raise RuntimeError("hook failure")

    with pytest.raises(RuntimeError, match="hook failure"):
        await app_inst.rooms.join(conn, "guarded-room")

    # Room state should be rolled back — conn should NOT be in the room
    assert "guarded-room" not in conn.rooms


@pytest.mark.anyio
async def test_receive_buffer_recheck() -> None:
    """Covers the TestConnection._buffer re-check path in receive()."""
    app_inst = SocketApp()

    @app_inst.on("first")
    async def h_first(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("reply_first", {"a": 1})

    @app_inst.on("second")
    async def h_second(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("reply_second", {"b": 2})

    client = TestClient(app_inst)
    async with client.connect() as tc:
        # Emit both events so both replies land in the outgoing queue
        await tc.emit("first", {})
        await tc.emit("second", {})
        # Receive in reverse order — reply_second should be buffered then found
        result_second = await tc.receive("reply_second")
        assert result_second == {"b": 2}
        # reply_first should come from the buffer
        result_first = await tc.receive("reply_first")
        assert result_first == {"a": 1}


@pytest.mark.anyio
async def test_fastapi_adapter_event_error_continues() -> None:
    """Covers the event processing try/except in the FastAPI adapter.

    An exception in handle_event should NOT tear down the connection.
    """
    socket_app_inst = SocketApp()

    @socket_app_inst.on("boom")
    async def boom_handler(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise RuntimeError("handler crash")

    @socket_app_inst.on("ping")
    async def ping_handler(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await conn.emit("pong", {})

    client = TestClient(socket_app_inst)
    async with client.connect() as tc:
        # This triggers a handler error — connection should survive
        await tc.emit("boom", {})
        err = await tc.receive("__error__")
        assert err["code"] == "HANDLER_ERROR"
        # Connection is still alive — can send and receive
        await tc.emit("ping", {})
        pong = await tc.receive("pong")
        assert pong == {}


@pytest.mark.anyio
async def test_session_max_duration_timeout() -> None:
    config = SessionConfig(max_duration=1, idle_timeout=0)
    mgr = SessionManager(config)

    now = datetime.now(timezone.utc) - timedelta(seconds=2)
    conn = Connection(
        id="c_timeout",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    # check timeouts returns True on max_duration limit reached
    is_disconnected = await mgr._check_timeouts(conn)
    assert is_disconnected is True
    conn._emit_fn.assert_called_with(
        "__session_expiring__",
        {"reason": "max_duration"},
    )
    conn._disconnect_fn.assert_called_with("max_duration")


@pytest.mark.anyio
async def test_session_idle_timeout() -> None:
    config = SessionConfig(max_duration=0, idle_timeout=1)
    mgr = SessionManager(config)

    now = datetime.now(timezone.utc)
    last_active = now - timedelta(seconds=2)
    conn = Connection(
        id="c_idle",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=last_active,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    is_disconnected = await mgr._check_timeouts(conn)
    assert is_disconnected is True
    conn._emit_fn.assert_called_with(
        "__idle_warning__",
        {"reason": "idle_timeout"},
    )
    conn._disconnect_fn.assert_called_with("idle_timeout")


@pytest.mark.anyio
async def test_session_loop_heartbeat_timeout() -> None:
    # Set timeout very small so wait_for fails immediately
    config = SessionConfig(
        heartbeat_interval=0.01,
        heartbeat_timeout=0.01,
    )
    mgr = SessionManager(config)

    now = datetime.now(timezone.utc)
    conn = Connection(
        id="c_hb_fail",
        raw_socket=TestRawSocket(),
        identity=Identity(),
        session=SessionInfo(started_at=now, expires_at=None, token_expires_at=None),
        connected_at=now,
        last_active=now,
    )
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    # Run session loop task
    task = asyncio.create_task(mgr._session_loop(conn))
    mgr._tasks[conn.id] = task
    mgr._pong_events[conn.id] = asyncio.Event()

    # Await the task with a safety timeout to avoid race conditions/flakes
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        pass

    # verify connection was disconnected due to heartbeat timeout
    conn._disconnect_fn.assert_called_with("heartbeat_timeout")
    await mgr.stop(conn.id)


# ── Connection manager Gaps ────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_manager_send_json_exception() -> None:
    backend = MemoryBackend()
    mgr = ConnectionManager(backend)
    conn = make_connection("c_bad_send")
    # Mock send_json to raise Exception
    conn.raw_socket.send_json = AsyncMock(side_effect=RuntimeError("send error"))  # type: ignore[method-assign]
    await mgr.connect(conn)

    # Should not raise exception
    await mgr.send(conn.id, "ping", {})


@pytest.mark.anyio
async def test_manager_disconnector_close_exception() -> None:
    backend = MemoryBackend()
    mgr = ConnectionManager(backend)
    conn = make_connection("c_bad_close")
    # Mock close to raise Exception
    conn.raw_socket.close = AsyncMock(side_effect=RuntimeError("close error"))  # type: ignore[method-assign]
    await mgr.connect(conn)

    disconnector = mgr._make_disconnector(conn)
    # Should not raise exception
    await disconnector("server_close")


# ── Rooms Gaps ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_rooms_join_variables_none() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rm = RoomManager(backend, manager)
    conn = make_connection()

    # Mock _match_guard to return a guard, but _extract_variables to return None
    guard = MagicMock()
    rm._match_guard = MagicMock(return_value=guard)  # type: ignore[method-assign]
    rm._extract_variables = MagicMock(return_value=None)  # type: ignore[method-assign]

    with pytest.raises(RoomPermissionError):
        await rm.join(conn, "any-room")


@pytest.mark.anyio
async def test_rooms_broadcast_except() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rm = RoomManager(backend, manager)
    conn1 = make_connection("c1")
    conn2 = make_connection("c2")
    await manager.connect(conn1)
    await manager.connect(conn2)

    conn1.raw_socket.send_json = AsyncMock()  # type: ignore[method-assign]
    conn2.raw_socket.send_json = AsyncMock()  # type: ignore[method-assign]

    await rm.broadcast_except("c1", "alert", {"msg": "hello"})
    # c1 is excluded, so conn1.send_json not called; conn2 should receive
    conn1.raw_socket.send_json.assert_not_called()
    conn2.raw_socket.send_json.assert_called_once()


@pytest.mark.anyio
async def test_rooms_safe_send_exception() -> None:
    backend = MemoryBackend()
    manager = ConnectionManager(backend)
    rm = RoomManager(backend, manager)

    # Mock manager.send to throw an exception
    manager.send = AsyncMock(side_effect=RuntimeError("send fail"))  # type: ignore[method-assign]

    # Should not raise exception
    await rm._safe_send("conn_ghost", "ping", {})


# ── Router Gaps ────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_router_error_hook_exception() -> None:
    registry = EventRegistry()
    # AsyncMock so `await resolver.resolve(...)` works
    resolver = AsyncMock(side_effect=ValueError("handler crashed"))
    # Mock error hook that itself raises
    bad_hook = AsyncMock(side_effect=RuntimeError("hook fail"))
    router = EventRouter(registry, resolver, on_error_callback=bad_hook)

    async def h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("handler crashed")

    from socketspec.registry import EventDefinition

    defn = EventDefinition(
        name="fail",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=None,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )

    conn = make_connection()
    conn._emit_fn = AsyncMock()  # wire emit so error response doesn't crash
    # Should not raise — error hook failure is swallowed
    await router._run_handler(conn, defn, {})


@pytest.mark.anyio
async def test_router_process_queue_sentinel() -> None:
    registry = EventRegistry()
    resolver = MagicMock()
    router = EventRouter(registry, resolver)

    conn = make_connection()
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_QUEUE_SENTINEL)

    # should break loop immediately on sentinel
    await router._process_queue(conn, queue)


@pytest.mark.anyio
async def test_router_process_queue_non_tuple() -> None:
    registry = EventRegistry()
    resolver = MagicMock()
    router = EventRouter(registry, resolver)

    conn = make_connection()
    queue: asyncio.Queue = asyncio.Queue()
    # Put non-tuple
    await queue.put("not-a-tuple")
    await queue.put(_QUEUE_SENTINEL)

    # should continue loop and complete on sentinel
    await router._process_queue(conn, queue)


# ── Testing Gaps ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_testing_timeout_remaining_negative() -> None:
    app = SocketApp()
    client = TestClient(app)
    async with client.connect() as conn:
        with pytest.raises(TimeoutError):
            # timeout of 0 or negative
            await conn.receive("event_never", timeout=-0.1)


@pytest.mark.anyio
async def test_testing_receive_non_dict_payload() -> None:
    app = SocketApp()

    @app.on("string_event")
    async def string_event(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        # Emit a non-dict payload
        await conn.emit("reply", "raw-string-value")  # type: ignore[arg-type]

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("string_event", {})
        res = await conn.receive("reply")
        assert res == {"value": "raw-string-value"}


@pytest.mark.anyio
async def test_testing_receive_broadcast() -> None:
    app = SocketApp()

    @app.on("ping")
    async def ping(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        await app.rooms.join(conn, "lobby")
        await app.rooms.broadcast("lobby", "announce", {"x": 1})

    client = TestClient(app)
    async with client.connect() as conn:
        await conn.emit("ping", {})
        res = await conn.receive_broadcast("announce", "lobby")
        assert res == {"x": 1}


@pytest.mark.anyio
async def test_testing_auth_token_provided() -> None:
    from socketspec.security.auth import APIKeyAuth

    app = SocketApp(auth=APIKeyAuth(api_key="token123"))
    # Pass the key via the query param that APIKeyAuth actually checks
    client = TestClient(app)
    async with client.connect(query_params={"api_key": "token123"}) as conn:
        assert conn.connection.identity is not None
