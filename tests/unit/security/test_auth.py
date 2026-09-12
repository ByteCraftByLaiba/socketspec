# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for JWTAuth and APIKeyAuth authentication backends."""

from __future__ import annotations

from datetime import datetime, timezone

import jwt
import pytest

from socketspec.security.auth import APIKeyAuth, JWTAuth

# ── JWTAuth ──────────────────────────────────────────────────────────────────


@pytest.fixture
def jwt_secret() -> str:
    return "test-secret-key-12345"


@pytest.mark.anyio
async def test_jwt_auth_valid_token_returns_identity(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode(
        {"sub": "user123", "scopes": ["read", "write"]}, jwt_secret, algorithm="HS256"
    )

    headers = {"Authorization": f"Bearer {token}"}
    identity = await auth.authenticate(headers, {})
    assert identity is not None
    assert identity.user_id == "user123"
    assert identity.scopes == ["read", "write"]
    assert identity.raw_token == token


@pytest.mark.anyio
async def test_jwt_auth_expired_token_returns_none(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "user123", "exp": 1}, jwt_secret, algorithm="HS256")

    headers = {"Authorization": f"Bearer {token}"}
    identity = await auth.authenticate(headers, {})
    assert identity is None


@pytest.mark.anyio
async def test_jwt_auth_wrong_secret_returns_none(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "user123"}, "wrong-secret", algorithm="HS256")

    headers = {"Authorization": f"Bearer {token}"}
    identity = await auth.authenticate(headers, {})
    assert identity is None


@pytest.mark.anyio
async def test_jwt_auth_malformed_token_returns_none(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    headers = {"Authorization": "Bearer malformed-token-xyz"}
    identity = await auth.authenticate(headers, {})
    assert identity is None


@pytest.mark.anyio
async def test_jwt_auth_missing_token_returns_none(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    identity = await auth.authenticate({}, {})
    assert identity is None


@pytest.mark.anyio
async def test_jwt_auth_reads_from_authorization_header(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "u1"}, jwt_secret)
    headers = {"authorization": token}
    identity = await auth.authenticate(headers, {})
    assert identity is not None
    assert identity.user_id == "u1"


@pytest.mark.anyio
async def test_jwt_auth_reads_from_query_param_token(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "u2"}, jwt_secret)
    identity = await auth.authenticate({}, {"token": token})
    assert identity is not None
    assert identity.user_id == "u2"


@pytest.mark.anyio
async def test_jwt_auth_bearer_prefix_stripped_correctly(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "u3"}, jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}
    identity = await auth.authenticate(headers, {})
    assert identity is not None
    assert identity.raw_token == token


@pytest.mark.anyio
async def test_jwt_auth_identity_contains_user_id_from_claims(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "u4"}, jwt_secret)
    identity = await auth.authenticate({"authorization": token}, {})
    assert identity is not None
    assert identity.user_id == "u4"


@pytest.mark.anyio
async def test_jwt_auth_identity_contains_scopes_from_claims(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    token = jwt.encode({"sub": "u5", "scopes": ["admin"]}, jwt_secret)
    identity = await auth.authenticate({"authorization": token}, {})
    assert identity is not None
    assert identity.scopes == ["admin"]


@pytest.mark.anyio
async def test_jwt_auth_identity_contains_token_expiry(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret)
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    token = jwt.encode({"sub": "u6", "exp": exp}, jwt_secret)
    identity = await auth.authenticate({"authorization": token}, {})
    assert identity is not None
    assert identity.token_expires_at is not None
    assert int(identity.token_expires_at.timestamp()) == exp


@pytest.mark.anyio
async def test_jwt_auth_none_algorithm_rejected(jwt_secret: str) -> None:
    auth = JWTAuth(secret=jwt_secret, algorithm="HS256")
    # algorithm="none" requires key=None in PyJWT; the resulting token is
    # encoded with HS256 expectations but decoded with HS256 verification —
    # verifying with a "none"-signed token should fail.
    token = jwt.encode({"sub": "u7"}, None, algorithm="none")  # type: ignore[arg-type]
    identity = await auth.authenticate({"authorization": token}, {})
    assert identity is None


# ── APIKeyAuth ────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_apikey_auth_valid_key_returns_identity() -> None:
    auth = APIKeyAuth(api_key="super-secret-key")
    headers = {"x-api-key": "super-secret-key"}
    identity = await auth.authenticate(headers, {})
    assert identity is not None


@pytest.mark.anyio
async def test_apikey_auth_wrong_key_returns_none() -> None:
    auth = APIKeyAuth(api_key="super-secret-key")
    headers = {"x-api-key": "wrong-key"}
    identity = await auth.authenticate(headers, {})
    assert identity is None


@pytest.mark.anyio
async def test_apikey_auth_missing_key_returns_none() -> None:
    auth = APIKeyAuth(api_key="super-secret-key")
    identity = await auth.authenticate({}, {})
    assert identity is None


@pytest.mark.anyio
async def test_apikey_auth_reads_from_header() -> None:
    auth = APIKeyAuth(api_key="key123")
    headers = {"x-api-key": "key123"}
    identity = await auth.authenticate(headers, {})
    assert identity is not None


@pytest.mark.anyio
async def test_apikey_auth_reads_from_query_param() -> None:
    auth = APIKeyAuth(api_key="key123")
    identity = await auth.authenticate({}, {"api_key": "key123"})
    assert identity is not None


@pytest.mark.anyio
async def test_apikey_auth_custom_header_name() -> None:
    auth = APIKeyAuth(api_key="key123", header="X-Custom-Key")
    headers = {"x-custom-key": "key123"}
    identity = await auth.authenticate(headers, {})
    assert identity is not None
