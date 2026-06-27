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

"""FastAPI-style dependency injection for socket event handlers.

Owns ``Depends()`` marker resolution and yield-based dependency cleanup.
Does NOT own handler execution or routing.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, cast

from socketspec.connection import Connection


class Depends:
    """Mark a handler parameter for dependency injection."""

    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


class DependencyResolver:
    """Resolves ``Depends()`` parameters from handler signatures."""

    async def resolve(
        self,
        handler: Callable[..., Any],
        conn: Connection,
        stack: AsyncExitStack,
    ) -> dict[str, Any]:
        """Resolve injected parameters for a handler or dependency callable.

        Args:
            handler: The callable whose ``Depends()`` defaults should be resolved.
            conn: The active connection passed to connection-aware dependencies.
            stack: Exit stack tracking yield-based dependency cleanup.

        Returns:
            Mapping of parameter names to resolved dependency values.
        """
        resolved: dict[str, Any] = {}
        signature = inspect.signature(handler)
        for name, param in signature.parameters.items():
            if name in resolved:
                continue
            if isinstance(param.default, Depends):
                value = await self._resolve_dependency(
                    param.default.dependency,
                    conn,
                    stack,
                )
                resolved[name] = value
            elif name == "conn":
                resolved[name] = conn
        return {
            key: value
            for key, value in resolved.items()
            if key in signature.parameters
        }

    async def _resolve_dependency(
        self,
        dependency: Callable[..., Any],
        conn: Connection,
        stack: AsyncExitStack,
    ) -> object:
        dep_kwargs = await self.resolve(dependency, conn, stack)
        result = dependency(**dep_kwargs)
        if inspect.isawaitable(result):
            result = await result
        if inspect.isasyncgen(result):
            async_gen = cast(AsyncGenerator[Any, None], result)
            return await stack.enter_async_context(_asyncgen_context(async_gen))
        return result


@asynccontextmanager
async def _asyncgen_context(
    generator: AsyncGenerator[Any, None],
) -> AsyncGenerator[Any, None]:
    value = await generator.__anext__()
    try:
        yield value
    finally:
        await generator.aclose()
