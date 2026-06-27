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

"""Middleware chain compilation and execution for socket events.

Owns middleware chaining compiled once at startup.
Does NOT own routing, validation, or handler execution.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from socketspec.connection import Connection
from socketspec.types import EventName, PayloadDict

NextHandler = Callable[[], Awaitable[None]]
MiddlewareFunc = Callable[
    [Connection, EventName, PayloadDict, NextHandler],
    Awaitable[None],
]
CompiledHandler = Callable[
    [Connection, EventName, PayloadDict],
    Awaitable[None],
]


class MiddlewareChain:
    """Builds and executes a FIFO middleware chain around the event router.

    Note:
        The chain is compiled once at startup via ``compile()``.
    """

    def __init__(self, middlewares: list[MiddlewareFunc]) -> None:
        self._chain = middlewares

    def compile(self, final_handler: CompiledHandler) -> CompiledHandler:
        """Compile middlewares into a single callable.

        Args:
            final_handler: The terminal handler, typically ``EventRouter.dispatch``.

        Returns:
            A callable that runs the full middleware chain then the final handler.
        """
        handler: CompiledHandler = final_handler
        for middleware in reversed(self._chain):
            handler = self._wrap(middleware, handler)
        return handler

    def _wrap(
        self,
        middleware: MiddlewareFunc,
        next_handler: CompiledHandler,
    ) -> CompiledHandler:
        async def wrapped(
            conn: Connection,
            event: EventName,
            payload: PayloadDict,
        ) -> None:
            async def call_next() -> None:
                await next_handler(conn, event, payload)

            await middleware(conn, event, payload, call_next)

        return wrapped
