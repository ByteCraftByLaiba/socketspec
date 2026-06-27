# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from socketspec.backends.memory import MemoryBackend
from socketspec.security.auth import JWTAuth


async def test_publish_callback_exception_is_logged(
    memory_backend: MemoryBackend,
) -> None:
    async def failing_callback(_message: dict[str, str]) -> None:
        raise RuntimeError("callback failed")

    await memory_backend.subscribe("channel", failing_callback)
    await memory_backend.publish("channel", {"event": "test"})


async def test_jwt_auth_reads_token_from_query_param() -> None:
    import jwt

    secret = "test-secret-key-with-enough-length"
    token = jwt.encode({"sub": "user-2"}, secret, algorithm="HS256")
    auth = JWTAuth(secret=secret)
    identity = await auth.authenticate({}, {"token": token})
    assert identity is not None
    assert identity.user_id == "user-2"


async def test_memory_backend_close_clears_state() -> None:
    backend = MemoryBackend()
    await backend.store_connection("c1", {})
    await backend.close()
    assert await backend.connection_exists("c1") is False
