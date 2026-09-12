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

"""Routes incoming socket events to registered handlers after validation.

Owns dispatch, payload validation, ordered queues, and handler error envelopes.
Does NOT own connection storage or middleware execution.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

from pydantic import BaseModel, ValidationError

from socketspec.connection import Connection
from socketspec.di import DependencyResolver
from socketspec.registry import EventDefinition, EventRegistry
from socketspec.types import ConnectionId, EventName, PayloadDict

logger = logging.getLogger(__name__)

_QUEUE_SENTINEL: object = object()
OrderedQueueItem = tuple[EventDefinition, Any] | object


OnErrorCallback = Callable[[Connection, Exception], Awaitable[None]]


class EventRouter:
    """Dispatches validated events to the correct handler."""

    def __init__(
        self,
        registry: EventRegistry,
        di_resolver: DependencyResolver,
        on_error_callback: OnErrorCallback | None = None,
    ) -> None:
        self._registry = registry
        self._di_resolver = di_resolver
        self._queues: dict[ConnectionId, asyncio.Queue[OrderedQueueItem]] = {}
        self._tasks: dict[ConnectionId, set[asyncio.Task[None]]] = {}
        self._on_error_callback = on_error_callback

    async def dispatch(
        self,
        conn: Connection,
        event: EventName,
        payload: PayloadDict,
    ) -> None:
        """Route an event to its handler after registry lookup and validation.

        Args:
            conn: The connection that sent the event.
            event: Event name from the wire envelope.
            payload: Raw payload dict from the client.
        """
        definition = self._registry.get(conn.namespace, event)
        if definition is None:
            await self._emit_error(
                conn,
                "UNKNOWN_EVENT",
                event,
                f"Unknown event: {event}",
            )
            return

        validated = await self._validate(conn, definition, payload)
        if validated is None:
            return

        if definition.ordered:
            await self._dispatch_ordered(conn, definition, validated)
            return

        task = asyncio.create_task(self._run_handler(conn, definition, validated))
        # Track so cleanup() can cancel if the connection drops mid-flight.
        self._tasks.setdefault(conn.id, set()).add(task)
        task.add_done_callback(lambda t: self._tasks.get(conn.id, set()).discard(t))

    async def cleanup(self, conn_id: ConnectionId) -> None:
        """Cancel in-flight handler tasks and drain ordered queue on disconnect.

        Args:
            conn_id: The disconnected connection id.
        """
        # Cancel any in-flight unordered handler tasks.
        for task in self._tasks.pop(conn_id, set()):
            task.cancel()

        # Signal the ordered queue worker to stop.
        queue = self._queues.pop(conn_id, None)
        if queue is not None:
            await queue.put(_QUEUE_SENTINEL)

    async def _validate(
        self,
        conn: Connection,
        definition: EventDefinition,
        payload: PayloadDict,
    ) -> BaseModel | PayloadDict | None:
        if definition.payload_model is None:
            return payload
        try:
            return definition.payload_model.model_validate(payload)
        except ValidationError as exc:
            await self._emit_error(
                conn,
                "VALIDATION_ERROR",
                definition.name,
                str(exc),
                {"errors": exc.errors()},
            )
            return None

    async def _run_handler(
        self,
        conn: Connection,
        definition: EventDefinition,
        payload: BaseModel | PayloadDict,
    ) -> None:
        stack = AsyncExitStack()
        try:
            injected = await self._di_resolver.resolve(
                definition.handler,
                conn,
                stack,
            )
            extra = {
                key: value
                for key, value in injected.items()
                if key not in ("conn", "payload")
            }
            await definition.handler(conn, payload, **extra)
        except Exception as exc:
            logger.error(
                "Handler failed for event %s on connection %s",
                definition.name,
                conn.id,
                exc_info=True,
            )
            await self._emit_error(
                conn,
                "HANDLER_ERROR",
                definition.name,
                str(exc),
            )
            if self._on_error_callback is not None:
                try:
                    await self._on_error_callback(conn, exc)
                except Exception:
                    logger.exception("Error lifecycle hook raised an exception")
        finally:
            await stack.aclose()

    async def _dispatch_ordered(
        self,
        conn: Connection,
        definition: EventDefinition,
        payload: BaseModel | PayloadDict,
    ) -> None:
        # setdefault is atomic within the event loop — no race between the
        # check and the insert that could spawn duplicate _process_queue tasks.
        if conn.id not in self._queues:
            queue: asyncio.Queue[OrderedQueueItem] = asyncio.Queue()
            self._queues[conn.id] = queue
            task = asyncio.create_task(self._process_queue(conn, queue))
            self._tasks.setdefault(conn.id, set()).add(task)
            task.add_done_callback(lambda t: self._tasks.get(conn.id, set()).discard(t))
        await self._queues[conn.id].put((definition, payload))

    async def _process_queue(
        self,
        conn: Connection,
        queue: asyncio.Queue[OrderedQueueItem],
    ) -> None:
        # Accepts the queue as a parameter to avoid KeyError if cleanup()
        # already popped it from self._queues before this task starts.
        while True:
            item = await queue.get()
            if item is _QUEUE_SENTINEL:
                queue.task_done()
                break
            if not isinstance(item, tuple):
                queue.task_done()
                continue
            definition, payload = item
            await self._run_handler(conn, definition, payload)
            queue.task_done()

    async def _emit_error(
        self,
        conn: Connection,
        code: str,
        event: EventName,
        message: str,
        details: PayloadDict | None = None,
    ) -> None:
        error_body: PayloadDict = {
            "code": code,
            "event": event,
            "message": message,
            "request_id": str(uuid.uuid4()),
            "details": details or {},
        }
        await conn.emit("__error__", error_body)
