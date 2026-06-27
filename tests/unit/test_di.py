# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from contextlib import AsyncExitStack

import pytest
from pydantic import BaseModel

from socketspec.app import SocketApp
from socketspec.connection import Connection
from socketspec.di import DependencyResolver, Depends
from socketspec.docs.engine import DocsEngine
from socketspec.registry import Emits
from socketspec.security.auth import APIKeyAuth
from socketspec.testing import TestClient
from tests.conftest import make_connection


class DocsPayload(BaseModel):
    text: str


async def test_depends_injects_resolved_value() -> None:
    resolver = DependencyResolver()

    async def get_value() -> str:
        return "injected"

    async def handler(
        conn: Connection,
        payload: dict[str, object],
        value: str = Depends(get_value),
    ) -> None:
        pass

    conn = make_connection("c1")
    stack = AsyncExitStack()
    resolved = await resolver.resolve(handler, conn, stack)
    assert resolved["value"] == "injected"
    await stack.aclose()


async def test_docs_engine_generates_event_schema() -> None:
    app = SocketApp()

    @app.on(
        "echo",
        description="Echo event",
        emits=[Emits("echoed", model=DocsPayload)],
    )
    async def handle_echo(conn: Connection, payload: DocsPayload) -> None:
        pass

    schema = DocsEngine(app._registry).generate_schema()
    assert schema["events"][0]["name"] == "echo"
    assert schema["events"][0]["payload"] is not None


async def test_connect_rejects_invalid_api_key() -> None:
    app = SocketApp(auth=APIKeyAuth(api_key="secret"))
    client = TestClient(app)
    with pytest.raises(RuntimeError, match="rejected"):
        async with client.connect(query_params={"api_key": "wrong"}):
            pass
