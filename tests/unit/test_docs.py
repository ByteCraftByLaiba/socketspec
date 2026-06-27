# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from socketspec.adapters.fastapi import mount
from socketspec.app import SocketApp


async def test_docs_index_requires_token_when_configured() -> None:
    socket_app = SocketApp(docs=True, docs_access_token="secret-token")
    app = FastAPI()
    mount(socket_app, app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get("/socket-docs")
        assert denied.status_code == 401
        allowed = await client.get("/socket-docs?token=secret-token")
        assert allowed.status_code == 200
