# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import jwt

from socketspec.security.auth import APIKeyAuth, JWTAuth


async def test_jwt_auth_returns_identity_for_valid_token() -> None:
    secret = "test-secret"
    token = jwt.encode({"sub": "user-1"}, secret, algorithm="HS256")
    auth = JWTAuth(secret=secret)
    identity = await auth.authenticate(
        {"authorization": f"Bearer {token}"},
        {},
    )
    assert identity is not None
    assert identity.user_id == "user-1"


async def test_jwt_auth_returns_none_for_invalid_token() -> None:
    auth = JWTAuth(secret="secret")
    identity = await auth.authenticate({"authorization": "Bearer bad"}, {})
    assert identity is None


async def test_api_key_auth_returns_identity_for_valid_key() -> None:
    auth = APIKeyAuth(api_key="abc123")
    identity = await auth.authenticate({"x-api-key": "abc123"}, {})
    assert identity is not None


async def test_api_key_auth_returns_none_for_invalid_key() -> None:
    auth = APIKeyAuth(api_key="abc123")
    identity = await auth.authenticate({"x-api-key": "wrong"}, {})
    assert identity is None
