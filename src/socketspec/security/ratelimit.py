# Copyright (c) 2025 Laiba Shahab. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Per-connection event rate limiting using a token bucket.

Owns rate-limit configuration and per-connection token state.
Does NOT own event routing or connection lifecycle.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from socketspec.types import ConnectionId

DEFAULT_RATE_LIMIT_EVENTS = 100
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass
class RateLimit:
    """Configuration for per-connection event rate limiting."""

    events: int = DEFAULT_RATE_LIMIT_EVENTS
    per_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


class TokenBucket:
    """Per-connection token bucket rate limiter.

    Note:
        Tokens refill continuously over time. All mutations use asyncio.Lock.
    """

    def __init__(self, config: RateLimit) -> None:
        self._max = float(config.events)
        self._refill_rate = config.events / config.per_seconds
        self._buckets: dict[ConnectionId, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, conn_id: ConnectionId) -> bool:
        """Attempt to consume one token for an incoming event.

        Args:
            conn_id: The connection requesting to send an event.

        Returns:
            True if the event is allowed, False if rate limited.
        """
        async with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(conn_id, (self._max, now))
            elapsed = now - last_refill
            tokens = min(self._max, tokens + elapsed * self._refill_rate)
            if tokens < 1:
                self._buckets[conn_id] = (tokens, now)
                return False
            self._buckets[conn_id] = (tokens - 1, now)
            return True

    async def remove(self, conn_id: ConnectionId) -> None:
        """Remove rate-limit state when a connection disconnects.

        Args:
            conn_id: The disconnected connection id.
        """
        async with self._lock:
            self._buckets.pop(conn_id, None)
