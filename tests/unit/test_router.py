# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for EventRouter — routing, validation, error wrapping, ordering."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from socketspec.connection import Connection
from socketspec.di import DependencyResolver
from socketspec.registry import EventDefinition, EventRegistry
from socketspec.router import EventRouter
from tests.conftest import make_connection


class MsgPayload(BaseModel):
    text: str = Field(min_length=1)
    num: int = 0


@pytest.fixture
def registry() -> EventRegistry:
    return EventRegistry()


@pytest.fixture
def di_resolver() -> DependencyResolver:
    return DependencyResolver()


@pytest.fixture
def router(registry: EventRegistry, di_resolver: DependencyResolver) -> EventRouter:
    return EventRouter(registry, di_resolver)


# ── Dispatch ──────────────────────────────────────────────────────────────────


async def test_dispatch_routes_to_correct_handler(
    router: EventRouter, registry: EventRegistry
) -> None:
    called = False

    async def h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        nonlocal called
        called = True

    defn = EventDefinition(
        name="test",
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
    registry.register(defn)

    conn = make_connection()
    await router.dispatch(conn, "test", {})
    # wait for task to run since unordered run in background tasks
    await asyncio.sleep(0.02)
    assert called is True


async def test_dispatch_unknown_event_emits_error(
    router: EventRouter, registry: EventRegistry
) -> None:
    conn = make_connection()
    conn._emit_fn = AsyncMock()

    await router.dispatch(conn, "ghost", {})
    conn._emit_fn.assert_called_once()
    args, _ = conn._emit_fn.call_args
    assert args[0] == "__error__"
    assert args[1]["code"] == "UNKNOWN_EVENT"


async def test_dispatch_validates_payload_with_pydantic(
    router: EventRouter, registry: EventRegistry
) -> None:
    called_payload = None

    async def h(conn: Connection, payload: MsgPayload) -> None:
        nonlocal called_payload
        called_payload = payload

    defn = EventDefinition(
        name="send",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=MsgPayload,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    await router.dispatch(conn, "send", {"text": "hello", "num": 42})
    await asyncio.sleep(0.02)
    assert called_payload is not None
    assert called_payload.text == "hello"
    assert called_payload.num == 42


async def test_dispatch_invalid_payload_emits_validation_error(
    router: EventRouter, registry: EventRegistry
) -> None:
    async def h(conn: Connection, payload: MsgPayload) -> None:
        pass

    defn = EventDefinition(
        name="send",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=MsgPayload,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    conn._emit_fn = AsyncMock()
    # "text" missing, violating validation
    await router.dispatch(conn, "send", {"num": 42})
    conn._emit_fn.assert_called_once()
    args, _ = conn._emit_fn.call_args
    assert args[0] == "__error__"
    assert args[1]["code"] == "VALIDATION_ERROR"


async def test_dispatch_missing_required_field_emits_validation_error(
    router: EventRouter, registry: EventRegistry
) -> None:
    async def h(conn: Connection, payload: MsgPayload) -> None:
        pass

    defn = EventDefinition(
        name="send",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=MsgPayload,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    conn._emit_fn = AsyncMock()
    await router.dispatch(conn, "send", {})
    args, _ = conn._emit_fn.call_args
    assert args[1]["code"] == "VALIDATION_ERROR"
    # should contain field details
    assert "text" in str(args[1]["details"])


async def test_dispatch_wrong_field_type_emits_validation_error(
    router: EventRouter, registry: EventRegistry
) -> None:
    async def h(conn: Connection, payload: MsgPayload) -> None:
        pass

    defn = EventDefinition(
        name="send",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=MsgPayload,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    conn._emit_fn = AsyncMock()
    await router.dispatch(conn, "send", {"text": "hello", "num": "not-an-int"})
    args, _ = conn._emit_fn.call_args
    assert args[1]["code"] == "VALIDATION_ERROR"


async def test_dispatch_handler_exception_emits_handler_error(
    router: EventRouter, registry: EventRegistry
) -> None:
    async def bad_h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("handler crashed")

    defn = EventDefinition(
        name="fail",
        namespace="/",
        handler=bad_h,  # type: ignore[arg-type]
        payload_model=None,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    conn._emit_fn = AsyncMock()
    await router.dispatch(conn, "fail", {})
    await asyncio.sleep(0.02)
    conn._emit_fn.assert_called_once()
    args, _ = conn._emit_fn.call_args
    assert args[0] == "__error__"
    assert args[1]["code"] == "HANDLER_ERROR"
    assert "handler crashed" in args[1]["message"]


async def test_dispatch_handler_exception_does_not_close_connection(
    router: EventRouter, registry: EventRegistry
) -> None:
    async def bad_h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        raise ValueError("crash")

    defn = EventDefinition(
        name="fail",
        namespace="/",
        handler=bad_h,  # type: ignore[arg-type]
        payload_model=None,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    conn._emit_fn = AsyncMock()
    conn._disconnect_fn = AsyncMock()

    await router.dispatch(conn, "fail", {})
    await asyncio.sleep(0.02)
    conn._disconnect_fn.assert_not_called()


# ── Ordering ──────────────────────────────────────────────────────────────────


async def test_ordered_events_run_sequentially(
    router: EventRouter, registry: EventRegistry
) -> None:
    sequence: list[int] = []

    async def h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        val = payload["val"]
        await asyncio.sleep(0.05 if val == 1 else 0.01)
        sequence.append(val)

    defn = EventDefinition(
        name="order",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=None,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=True,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    # dispatch 1 and then 2 immediately
    await router.dispatch(conn, "order", {"val": 1})
    await router.dispatch(conn, "order", {"val": 2})

    # wait for both to complete
    await asyncio.sleep(0.1)
    # ordering guarantees 1 runs first to completion before 2 starts
    assert sequence == [1, 2]
    await router.cleanup(conn.id)


async def test_unordered_events_run_concurrently(
    router: EventRouter, registry: EventRegistry
) -> None:
    sequence: list[int] = []

    async def h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        val = payload["val"]
        await asyncio.sleep(0.05 if val == 1 else 0.01)
        sequence.append(val)

    defn = EventDefinition(
        name="unorder",
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
    registry.register(defn)

    conn = make_connection()
    await router.dispatch(conn, "unorder", {"val": 1})
    await router.dispatch(conn, "unorder", {"val": 2})

    await asyncio.sleep(0.1)
    # unordered starts both concurrent, so 2 finishes before 1
    assert sequence == [2, 1]


async def test_cleanup_removes_ordered_queue(
    router: EventRouter, registry: EventRegistry
) -> None:
    async def h(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        pass

    defn = EventDefinition(
        name="order",
        namespace="/",
        handler=h,  # type: ignore[arg-type]
        payload_model=None,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=True,
        executor=False,
    )
    registry.register(defn)

    conn = make_connection()
    await router.dispatch(conn, "order", {})
    assert conn.id in router._queues
    await router.cleanup(conn.id)
    assert conn.id not in router._queues


# ── Error details ─────────────────────────────────────────────────────────────


async def test_error_envelope_contains_required_fields(
    router: EventRouter, registry: EventRegistry
) -> None:
    conn = make_connection()
    conn._emit_fn = AsyncMock()

    await router.dispatch(conn, "ghost", {})
    args, _ = conn._emit_fn.call_args
    body = args[1]
    assert "request_id" in body
    assert body["code"] == "UNKNOWN_EVENT"
    assert body["event"] == "ghost"
    assert "message" in body
