# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from starlette.testclient import TestClient as StarletteTestClient

from socketspec.adapters.fastapi import mount
from socketspec.app import SocketApp


class EchoPayload(BaseModel):
    text: str


def test_fastapi_mount_handles_websocket_echo() -> None:
    socket_app = SocketApp()

    @socket_app.on("echo")
    async def handle_echo(conn: object, payload: EchoPayload) -> None:
        await conn.emit("echoed", payload.model_dump())

    app = FastAPI()
    mount(socket_app, app, path="/ws")
    socket_app._startup_validate()

    with StarletteTestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://test"}) as ws:
            ws.send_json({"event": "echo", "payload": {"text": "hello"}})
            message = ws.receive_json()
            assert message["event"] == "echoed"
            assert message["payload"]["text"] == "hello"


async def test_docs_schema_endpoint_returns_events() -> None:
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
        assert response.status_code == 200
        data = response.json()
        assert data["events"][0]["name"] == "ping"
