# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for TokenBucket rate limiter."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from socketspec.security.ratelimit import RateLimit, TokenBucket


@pytest.mark.anyio
async def test_within_limit_returns_true() -> None:
    limiter = TokenBucket(RateLimit(events=5, per_seconds=60))
    assert await limiter.consume("conn-1") is True


@pytest.mark.anyio
async def test_exceeding_limit_returns_false() -> None:
    limiter = TokenBucket(RateLimit(events=2, per_seconds=60))
    assert await limiter.consume("conn-1") is True
    assert await limiter.consume("conn-1") is True
    assert await limiter.consume("conn-1") is False


@pytest.mark.anyio
async def test_limit_applies_per_connection() -> None:
    limiter = TokenBucket(RateLimit(events=1, per_seconds=60))
    assert await limiter.consume("conn-1") is True
    assert await limiter.consume("conn-2") is True
    assert await limiter.consume("conn-1") is False
    assert await limiter.consume("conn-2") is False


@pytest.mark.anyio
async def test_different_connections_have_independent_buckets() -> None:
    limiter = TokenBucket(RateLimit(events=5, per_seconds=60))
    await limiter.consume("conn-1")
    assert "conn-1" in limiter._buckets
    assert "conn-2" not in limiter._buckets


@pytest.mark.anyio
async def test_remove_cleans_up_bucket() -> None:
    limiter = TokenBucket(RateLimit(events=5, per_seconds=60))
    await limiter.consume("conn-1")
    assert "conn-1" in limiter._buckets
    await limiter.remove("conn-1")
    assert "conn-1" not in limiter._buckets


@pytest.mark.anyio
async def test_remove_nonexistent_connection_does_not_raise() -> None:
    limiter = TokenBucket(RateLimit(events=5, per_seconds=60))
    await limiter.remove("ghost")


@pytest.mark.anyio
async def test_bucket_refills_over_time() -> None:
    import time

    limiter = TokenBucket(RateLimit(events=1, per_seconds=1))
    start = time.monotonic()
    assert await limiter.consume("conn-1") is True
    assert await limiter.consume("conn-1") is False

    # Simulate time passing via side_effect — each call to time.monotonic()
    # returns the next value in the list.
    with patch(
        "socketspec.security.ratelimit.time.monotonic",
        side_effect=[start + 1.1, start + 1.1],
    ):
        assert await limiter.consume("conn-1") is True


@pytest.mark.anyio
async def test_zero_events_limit_always_blocks() -> None:
    limiter = TokenBucket(RateLimit(events=0, per_seconds=10))
    assert await limiter.consume("conn-1") is False


@pytest.mark.anyio
async def test_concurrent_consumes_from_same_connection() -> None:
    limiter = TokenBucket(RateLimit(events=10, per_seconds=10))
    results = await asyncio.gather(*[limiter.consume("conn-1") for _ in range(5)])
    assert all(results)
    # token count is 10 - 5 = 5; allow tiny float drift from elapsed time
    import pytest

    assert limiter._buckets["conn-1"][0] == pytest.approx(5.0, abs=0.1)
