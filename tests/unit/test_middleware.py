# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for MiddlewareChain — compilation, FIFO execution, abort, parameter passing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from socketspec.connection import Connection
from socketspec.middleware import MiddlewareChain
from tests.conftest import make_connection


def test_empty_middleware_chain_calls_final_handler() -> None:
    calls: list[str] = []

    async def final_handler(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        calls.append("final")

    chain = MiddlewareChain([])
    compiled = chain.compile(final_handler)

    conn = make_connection("c1")
    # run compiled chain
    import anyio

    anyio.run(compiled, conn, "ping", {})
    assert calls == ["final"]


def test_single_middleware_executes_before_handler() -> None:
    calls: list[str] = []

    async def middleware(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append("mid")
        await call_next()

    async def final_handler(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        calls.append("final")

    chain = MiddlewareChain([middleware])  # type: ignore[list-item]
    compiled = chain.compile(final_handler)

    conn = make_connection("c2")
    import anyio

    anyio.run(compiled, conn, "ping", {})
    assert calls == ["mid", "final"]


def test_middleware_order_is_fifo() -> None:
    calls: list[str] = []

    async def m1(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append("m1")
        await call_next()

    async def m2(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append("m2")
        await call_next()

    async def final_handler(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        calls.append("final")

    chain = MiddlewareChain([m1, m2])  # type: ignore[list-item]
    compiled = chain.compile(final_handler)

    conn = make_connection("c3")
    import anyio

    anyio.run(compiled, conn, "ping", {})
    assert calls == ["m1", "m2", "final"]


def test_middleware_can_abort_chain_by_not_calling_next() -> None:
    calls: list[str] = []

    async def abort_mid(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append("abort")
        # do not call await call_next()

    async def final_handler(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        calls.append("final")

    chain = MiddlewareChain([abort_mid])  # type: ignore[list-item]
    compiled = chain.compile(final_handler)

    conn = make_connection("c4")
    import anyio

    anyio.run(compiled, conn, "ping", {})
    assert calls == ["abort"]


def test_middleware_receives_correct_arguments() -> None:
    passed_args: dict[str, object] = {}

    async def track(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        passed_args["conn"] = conn
        passed_args["event"] = event
        passed_args["payload"] = payload
        await call_next()

    async def final_handler(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        pass

    chain = MiddlewareChain([track])  # type: ignore[list-item]
    compiled = chain.compile(final_handler)

    conn = make_connection("c5")
    payload = {"data": "test"}
    import anyio

    anyio.run(compiled, conn, "my_event", payload)
    assert passed_args["conn"] is conn
    assert passed_args["event"] == "my_event"
    assert passed_args["payload"] is payload


def test_chain_compiled_once_not_per_call() -> None:
    # Compile happens during compilation step, not during wrapping call.
    # We can mock reversing/wrapping of the chain
    calls: list[str] = []

    async def m1(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append("m1")
        await call_next()

    chain = MiddlewareChain([m1])  # type: ignore[list-item]
    final = AsyncMock()
    compiled = chain.compile(final)

    conn = make_connection("c6")
    import anyio

    anyio.run(compiled, conn, "ping", {})
    anyio.run(compiled, conn, "ping", {})
    assert calls == ["m1", "m1"]


async def test_middleware_exception_propagates_correctly() -> None:
    async def failing_mid(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        raise ValueError("mid error")

    async def final_handler(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        pass

    chain = MiddlewareChain([failing_mid])  # type: ignore[list-item]
    compiled = chain.compile(final_handler)

    conn = make_connection("c7")
    with pytest.raises(ValueError, match="mid error"):
        await compiled(conn, "ping", {})


async def test_multiple_middlewares_all_execute_in_order() -> None:
    calls: list[int] = []

    async def m1(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append(1)
        await call_next()
        calls.append(11)

    async def m2(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        calls.append(2)
        await call_next()
        calls.append(22)

    async def final(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        calls.append(3)

    chain = MiddlewareChain([m1, m2])  # type: ignore[list-item]
    compiled = chain.compile(final)

    conn = make_connection("c8")
    await compiled(conn, "ping", {})
    # FIFO for prefix path: 1 runs, calls next (which is m2), 2 runs, calls final (3),
    # then stack unwinds: 22 runs, then 11 runs.
    assert calls == [1, 2, 3, 22, 11]


async def test_middleware_can_modify_payload_before_handler() -> None:
    modified_payload: dict = {}  # type: ignore[type-arg]

    async def modify(
        conn: Connection, event: str, payload: dict, call_next: callable
    ) -> None:  # type: ignore[type-arg,valid-type]
        payload["modified"] = True
        await call_next()

    async def final(conn: Connection, event: str, payload: dict) -> None:  # type: ignore[type-arg]
        nonlocal modified_payload
        modified_payload = payload

    chain = MiddlewareChain([modify])  # type: ignore[list-item]
    compiled = chain.compile(final)

    conn = make_connection("c9")
    payload: dict = {}  # type: ignore[type-arg]
    await compiled(conn, "ping", payload)
    assert modified_payload.get("modified") is True
