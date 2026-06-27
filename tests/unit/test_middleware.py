# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from socketspec.connection import Connection
from socketspec.middleware import MiddlewareChain
from socketspec.types import PayloadDict


async def test_single_middleware_executes_before_handler() -> None:
    order: list[str] = []

    async def middleware(
        conn: Connection,
        event: str,
        payload: PayloadDict,
        call_next: object,
    ) -> None:
        order.append("middleware")
        await call_next()

    async def handler(
        conn: Connection,
        event: str,
        payload: PayloadDict,
    ) -> None:
        order.append("handler")

    chain = MiddlewareChain([middleware]).compile(handler)
    from tests.conftest import make_connection

    await chain(make_connection("mw"), "evt", {})
    assert order == ["middleware", "handler"]


async def test_middleware_order_is_fifo() -> None:
    order: list[str] = []

    async def first(
        conn: Connection,
        event: str,
        payload: PayloadDict,
        call_next: object,
    ) -> None:
        order.append("first")
        await call_next()

    async def second(
        conn: Connection,
        event: str,
        payload: PayloadDict,
        call_next: object,
    ) -> None:
        order.append("second")
        await call_next()

    async def handler(
        conn: Connection,
        event: str,
        payload: PayloadDict,
    ) -> None:
        order.append("handler")

    chain = MiddlewareChain([first, second]).compile(handler)
    from tests.conftest import make_connection

    await chain(make_connection("mw2"), "evt", {})
    assert order == ["first", "second", "handler"]


async def test_middleware_can_abort_chain_without_call_next() -> None:
    ran_handler = False

    async def blocking(
        conn: Connection,
        event: str,
        payload: PayloadDict,
        call_next: object,
    ) -> None:
        return

    async def handler(
        conn: Connection,
        event: str,
        payload: PayloadDict,
    ) -> None:
        nonlocal ran_handler
        ran_handler = True

    chain = MiddlewareChain([blocking]).compile(handler)
    from tests.conftest import make_connection

    await chain(make_connection("mw3"), "evt", {})
    assert ran_handler is False
