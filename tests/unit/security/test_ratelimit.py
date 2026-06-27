# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from socketspec.security.ratelimit import RateLimit, TokenBucket


async def test_consume_within_limit_returns_true() -> None:
    limiter = TokenBucket(RateLimit(events=2, per_seconds=60))
    assert await limiter.consume("conn-1") is True
    assert await limiter.consume("conn-1") is True


async def test_consume_over_limit_returns_false() -> None:
    limiter = TokenBucket(RateLimit(events=1, per_seconds=60))
    assert await limiter.consume("conn-1") is True
    assert await limiter.consume("conn-1") is False


async def test_remove_clears_connection_bucket() -> None:
    limiter = TokenBucket(RateLimit(events=1, per_seconds=60))
    await limiter.consume("conn-1")
    await limiter.remove("conn-1")
    assert await limiter.consume("conn-1") is True
