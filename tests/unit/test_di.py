# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for DependencyResolver — single, chained, yield-based deps and lifecycle."""

from __future__ import annotations

from contextlib import AsyncExitStack

import pytest

from socketspec.connection import Connection
from socketspec.di import DependencyResolver, Depends
from tests.conftest import make_connection


@pytest.fixture
def resolver() -> DependencyResolver:
    return DependencyResolver()


async def test_no_depends_returns_empty_dict(resolver: DependencyResolver) -> None:
    async def handler(conn: Connection, payload: dict) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        injected = await resolver.resolve(handler, conn, stack)
        assert injected == {"conn": conn}


async def test_single_depends_resolved(resolver: DependencyResolver) -> None:
    def dep() -> str:
        return "value"

    async def handler(conn: Connection, payload: dict, val: str = Depends(dep)) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        injected = await resolver.resolve(handler, conn, stack)
        assert injected == {"conn": conn, "val": "value"}


async def test_chained_depends_resolved_in_order(resolver: DependencyResolver) -> None:
    calls: list[str] = []

    def dep_a() -> str:
        calls.append("a")
        return "A"

    def dep_b(a: str = Depends(dep_a)) -> str:
        calls.append("b")
        return a + "B"

    async def handler(
        conn: Connection, payload: dict, val: str = Depends(dep_b)
    ) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        injected = await resolver.resolve(handler, conn, stack)
        assert injected == {"conn": conn, "val": "AB"}
        assert calls == ["a", "b"]


async def test_depends_receives_connection_object(resolver: DependencyResolver) -> None:
    received_conn = None

    def dep(conn: Connection) -> str:
        nonlocal received_conn
        received_conn = conn
        return "ok"

    async def handler(conn: Connection, payload: dict, val: str = Depends(dep)) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        await resolver.resolve(handler, conn, stack)
        assert received_conn is conn


async def test_yield_depends_cleanup_called_after_handler(
    resolver: DependencyResolver,
) -> None:
    calls: list[str] = []

    async def dep() -> object:
        calls.append("start")
        try:
            yield "resource"
        finally:
            calls.append("cleanup")

    async def handler(
        conn: Connection, payload: dict, val: object = Depends(dep)
    ) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        injected = await resolver.resolve(handler, conn, stack)
        assert injected["val"] == "resource"
        assert calls == ["start"]
    # exit stack closed here — finally block runs
    assert calls == ["start", "cleanup"]


async def test_depends_exception_propagates(resolver: DependencyResolver) -> None:
    def bad_dep() -> None:
        raise ValueError("dep error")

    async def handler(
        conn: Connection, payload: dict, val: None = Depends(bad_dep)
    ) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        with pytest.raises(ValueError, match="dep error"):
            await resolver.resolve(handler, conn, stack)


async def test_same_depends_used_by_two_deps_is_called_twice(
    resolver: DependencyResolver,
) -> None:
    """DependencyResolver does not deduplicate/cache dependencies.

    The same leaf factory used by two separate deps is called once per dep,
    not once overall. This is intentional — caching is left to the user.
    """
    calls = 0

    def leaf() -> str:
        nonlocal calls
        calls += 1
        return "leaf"

    def dep1(v: str = Depends(leaf)) -> str:
        return v + "1"

    def dep2(v: str = Depends(leaf)) -> str:
        return v + "2"

    async def handler(
        conn: Connection,
        payload: dict,  # type: ignore[type-arg]
        d1: str = Depends(dep1),
        d2: str = Depends(dep2),
    ) -> None:
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        injected = await resolver.resolve(handler, conn, stack)
        assert injected["d1"] == "leaf1"
        assert injected["d2"] == "leaf2"
        # Resolver does NOT deduplicate: leaf is called once per dep that uses it.
        assert calls == 2


async def test_depends_with_no_params_resolved(resolver: DependencyResolver) -> None:
    def no_param_dep() -> int:
        return 42

    async def handler(
        conn: Connection, payload: dict, num: int = Depends(no_param_dep)
    ) -> None:  # type: ignore[type-arg]
        pass

    conn = make_connection()
    async with AsyncExitStack() as stack:
        injected = await resolver.resolve(handler, conn, stack)
        assert injected["num"] == 42
