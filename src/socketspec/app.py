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

"""Main SocketSpec application class and connection lifecycle orchestration.

Owns decorator registration, security layer ordering, and lifecycle hooks.
Does NOT own raw WebSocket transport or framework-specific adapters.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal, get_type_hints

from pydantic import BaseModel

from socketspec.backends.base import BackendAdapter
from socketspec.backends.memory import MemoryBackend
from socketspec.connection import Connection, Identity, RawSocket, SessionInfo
from socketspec.di import DependencyResolver
from socketspec.manager import ConnectionManager
from socketspec.middleware import CompiledHandler, MiddlewareChain, MiddlewareFunc
from socketspec.registry import Broadcasts, Emits, EventDefinition, EventRegistry
from socketspec.rooms import Room, RoomGuardFunc, RoomManager
from socketspec.router import EventRouter
from socketspec.security.auth import AuthBackend
from socketspec.security.origins import OriginValidator
from socketspec.security.ratelimit import RateLimit, TokenBucket
from socketspec.session import SessionConfig, SessionManager
from socketspec.types import EventName, HandlerFunc

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAYLOAD_SIZE = 65_536
HTTP_FORBIDDEN_CLOSE_CODE = 403
AUTH_FAILURE_CLOSE_CODE = 4001
LifecycleHook = Callable[..., Awaitable[None]]


class SocketApp:
    """FastAPI-style WebSocket application entry point."""

    def __init__(
        self,
        *,
        docs: bool = False,
        docs_url: str = "/socket-docs",
        docs_access_token: str | None = None,
        auth: AuthBackend | None = None,
        backend: Literal["memory"] | BackendAdapter = "memory",
        allowed_origins: list[str] | None = None,
        max_payload_size: int = DEFAULT_MAX_PAYLOAD_SIZE,
        rate_limit: RateLimit | None = None,
        session: SessionConfig | None = None,
        rooms: list[Room] | None = None,
        namespace: str = "/",
        debug: bool = False,
        debug_url: str = "/socket-debug",
    ) -> None:
        origins = allowed_origins if allowed_origins is not None else ["*"]
        self._namespace = namespace
        self._registry = EventRegistry()
        self._backend = self._build_backend(backend)
        self._manager = ConnectionManager(self._backend)
        self._session_mgr = SessionManager(session or SessionConfig())
        self._origin_validator = OriginValidator(origins)
        self._rate_limiter = TokenBucket(rate_limit) if rate_limit else None
        self._di_resolver = DependencyResolver()
        self._middlewares: list[MiddlewareFunc] = []
        self._router = EventRouter(self._registry, self._di_resolver)
        self.rooms = RoomManager(self._backend, self._manager)
        self._auth = auth
        self._max_payload_size = max_payload_size
        self._docs = docs
        self._docs_url = docs_url
        self._docs_access_token = docs_access_token
        self._debug = debug
        self._debug_url = debug_url
        # Single source-of-truth queue kept for backward compat with tests that
        # put_nowait directly. SSE clients each get their own queue via
        # _debug_subscribe / _debug_unsubscribe (fan-out pattern).
        self._debug_queue: asyncio.Queue[dict[str, Any] | None] | None = (
            asyncio.Queue(maxsize=500) if debug else None
        )
        # Per-client SSE subscriber queues (fan-out). Each connected debug tab
        # holds a reference; _debug_log broadcasts to all of them.
        self._debug_subscribers: list[asyncio.Queue[dict[str, Any] | None]] = []
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._lifecycle_hooks: dict[str, list[LifecycleHook]] = {
            "connect": [],
            "disconnect": [],
            "error": [],
            "room_join": [],
            "room_leave": [],
        }
        self._compiled_chain: CompiledHandler = self._router.dispatch
        # Wire error lifecycle hooks into the router now that the hooks dict exists.
        self._router._on_error_callback = self._run_error_hooks

        for room in rooms or []:
            self.rooms.register_static(room.name)

        self.rooms.register_join_hook(self._run_room_join_hooks)

    def on(
        self,
        event: EventName,
        *,
        description: str = "",
        tags: list[str] | None = None,
        emits: list[Emits] | None = None,
        broadcasts: list[Broadcasts] | None = None,
        ordered: bool = False,
        executor: bool = False,
        deprecated: bool = False,
    ) -> Callable[[HandlerFunc], HandlerFunc]:
        """Register an event handler."""

        def decorator(func: HandlerFunc) -> HandlerFunc:
            definition = EventDefinition(
                name=event,
                namespace=self._namespace,
                handler=func,
                payload_model=self._infer_payload_model(func),
                emits=emits or [],
                broadcasts=broadcasts or [],
                description=description,
                tags=tags or [],
                ordered=ordered,
                executor=executor,
                deprecated=deprecated,
            )
            self._registry.register(definition)
            return func

        return decorator

    def middleware(self, func: MiddlewareFunc) -> MiddlewareFunc:
        """Register middleware that runs before each event handler."""
        self._middlewares.append(func)
        return func

    def on_connect(self, func: LifecycleHook) -> LifecycleHook:
        """Register a hook that runs after a connection is established."""
        self._lifecycle_hooks["connect"].append(func)
        return func

    def on_disconnect(self, func: LifecycleHook) -> LifecycleHook:
        """Register a hook that runs after a connection is torn down."""
        self._lifecycle_hooks["disconnect"].append(func)
        return func

    def on_error(self, func: LifecycleHook) -> LifecycleHook:
        """Register a hook that runs when handler errors are emitted."""
        self._lifecycle_hooks["error"].append(func)
        return func

    def on_room_join(self, func: LifecycleHook) -> LifecycleHook:
        """Register a hook that runs after a connection joins a room."""
        self._lifecycle_hooks["room_join"].append(func)
        return func

    def on_room_leave(self, func: LifecycleHook) -> LifecycleHook:
        """Register a hook that runs after a connection leaves a room."""
        self._lifecycle_hooks["room_leave"].append(func)
        return func

    def room_guard(
        self,
        pattern: str,
    ) -> Callable[[RoomGuardFunc], RoomGuardFunc]:
        """Protect a room name pattern with a permission function."""

        def decorator(func: RoomGuardFunc) -> RoomGuardFunc:
            self.rooms.register_guard(pattern, func)
            return func

        return decorator

    async def handle_connect(
        self,
        raw_socket: RawSocket,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Connection | None:
        """Accept and register a new WebSocket connection."""
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        origin = normalized_headers.get("origin")
        if not self._origin_validator.is_allowed(origin):
            await raw_socket.close(code=HTTP_FORBIDDEN_CLOSE_CODE)
            return None

        identity = Identity()
        if self._auth is not None:
            auth_result = await self._auth.authenticate(headers, query_params)
            if auth_result is None:
                await self._emit_raw(
                    raw_socket,
                    "AUTH_ERROR",
                    "__connect__",
                    "Authentication failed",
                )
                await raw_socket.close(code=AUTH_FAILURE_CLOSE_CODE)
                return None
            identity = auth_result

        conn = self._build_connection(
            raw_socket,
            identity,
            headers,
            query_params,
        )
        await self._manager.connect(conn, full_lifecycle=self.handle_disconnect)
        await self._session_mgr.start(conn)

        for hook in self._lifecycle_hooks["connect"]:
            await hook(conn)

        logger.info("Connection %s established", conn.id)
        self._debug_log(
            {
                "type": "connect",
                "conn_id": conn.id,
                "user_id": conn.identity.user_id,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        return conn

    async def handle_event(
        self,
        conn: Connection,
        raw_message: str | bytes,
    ) -> None:
        """Handle one inbound client message."""
        size = (
            len(raw_message)
            if isinstance(raw_message, bytes)
            else len(raw_message.encode())
        )
        if size > self._max_payload_size:
            await conn.emit("__error__", {"code": "PAYLOAD_TOO_LARGE"})
            return

        try:
            if isinstance(raw_message, bytes):
                raw_message = raw_message.decode()
            data = json.loads(raw_message)
            event = data["event"]
            payload = data.get("payload", {})
            if not isinstance(payload, dict):
                raise TypeError("payload must be an object")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await conn.emit(
                "__error__",
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid message format",
                },
            )
            return

        # __pong__ is a system frame — check before rate limiting so heartbeat
        # responses never consume rate-limit tokens.
        if event == "__pong__":
            self._session_mgr.signal_pong(conn.id)
            return

        if self._rate_limiter is not None:
            allowed = await self._rate_limiter.consume(conn.id)
            if not allowed:
                await conn.emit("__error__", {"code": "RATE_LIMIT_ERROR"})
                return

        await self._session_mgr.touch(conn)
        self._debug_log(
            {
                "type": "event",
                "conn_id": conn.id,
                "event": event,
                "payload_size": size,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self._compiled_chain(conn, event, payload)

    async def handle_disconnect(
        self,
        conn: Connection,
        reason: str = "client_close",
    ) -> None:
        """Tear down a connection and run lifecycle cleanup."""
        await self._session_mgr.stop(conn.id)

        # Leave all rooms first so conn.rooms is fully cleared before hooks run.
        rooms_snapshot = list(conn.rooms)
        for room in rooms_snapshot:
            await self.rooms.leave(conn, room)

        # Fire room_leave hooks after all rooms are left, with error isolation.
        for room in rooms_snapshot:
            for hook in self._lifecycle_hooks["room_leave"]:
                try:
                    await hook(conn, room)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "room_leave hook failed for conn=%s room=%s", conn.id, room
                    )

        await self._manager.disconnect(conn)

        for hook in self._lifecycle_hooks["disconnect"]:
            try:
                await hook(conn, reason)
            except Exception:  # noqa: BLE001
                logger.exception("disconnect hook failed for conn=%s", conn.id)

        if self._rate_limiter is not None:
            await self._rate_limiter.remove(conn.id)

        await self._router.cleanup(conn.id)
        logger.info("Connection %s disconnected: %s", conn.id, reason)
        self._debug_log(
            {
                "type": "disconnect",
                "conn_id": conn.id,
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _startup_validate(self) -> None:
        """Run startup validation and compile middleware before serving."""
        self._registry.validate()
        self._compiled_chain = MiddlewareChain(self._middlewares).compile(
            self._router.dispatch
        )

    async def _graceful_shutdown(self) -> None:
        """Release backend resources on application shutdown."""
        # Signal shutdown immediately so SSE streams can exit without blocking.
        self._shutdown_event.set()
        if self._debug_queue is not None:
            try:
                self._debug_queue.put_nowait(None)
            except Exception:  # noqa: BLE001
                pass
        await self._backend.close()

    async def _run_room_join_hooks(self, conn: Connection, room: str) -> None:
        for hook in self._lifecycle_hooks["room_join"]:
            await hook(conn, room)

    async def _run_error_hooks(self, conn: Connection, exc: Exception) -> None:
        """Invoke all registered error lifecycle hooks."""
        for hook in self._lifecycle_hooks["error"]:
            try:
                await hook(conn, exc)
            except Exception:
                logger.exception("Error lifecycle hook raised an exception")

    def _debug_subscribe(self) -> asyncio.Queue[dict[str, Any] | None]:
        """Register a new per-client SSE queue and return it."""
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=500)
        self._debug_subscribers.append(q)
        return q

    def _debug_unsubscribe(self, q: asyncio.Queue[dict[str, Any] | None]) -> None:
        """Remove a per-client SSE queue when the client disconnects."""
        try:
            self._debug_subscribers.remove(q)
        except ValueError:
            pass

    def _debug_log(self, entry: dict[str, Any]) -> None:
        """Broadcast a debug log entry to all active SSE subscribers.

        Each connected debug tab has its own queue so no client starves
        another. Oldest entries are evicted when a subscriber queue is full.
        """
        if not self._debug:
            return
        # Also feed the legacy _debug_queue for tests that read it directly.
        if self._debug_queue is not None:
            try:
                self._debug_queue.put_nowait(entry)
            except asyncio.QueueFull:
                try:
                    self._debug_queue.get_nowait()
                    self._debug_queue.put_nowait(entry)
                except Exception:  # noqa: BLE001
                    pass
        for q in list(self._debug_subscribers):
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(entry)
                except Exception:  # noqa: BLE001
                    pass

    def _build_backend(
        self,
        backend: Literal["memory"] | BackendAdapter,
    ) -> BackendAdapter:
        if backend == "memory":
            return MemoryBackend()
        return backend

    def _build_connection(
        self,
        raw_socket: RawSocket,
        identity: Identity,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Connection:
        now = datetime.now(timezone.utc)
        session = SessionInfo(
            started_at=now,
            expires_at=None,
            token_expires_at=identity.token_expires_at,
        )
        return Connection(
            id=str(uuid.uuid4()),
            raw_socket=raw_socket,
            identity=identity,
            session=session,
            connected_at=now,
            last_active=now,
            headers=headers,
            query_params=query_params,
            namespace=self._namespace,
        )

    async def _emit_raw(
        self,
        raw_socket: RawSocket,
        code: str,
        event: EventName,
        message: str,
    ) -> None:
        await raw_socket.send_json(
            {
                "event": "__error__",
                "payload": {
                    "code": code,
                    "event": event,
                    "message": message,
                    "request_id": str(uuid.uuid4()),
                    "details": {},
                },
            }
        )

    def _infer_payload_model(self, func: Callable[..., Any]) -> type[BaseModel] | None:
        params = list(inspect.signature(func).parameters.values())
        if len(params) < 2:
            return None
        param = params[1]
        annotation: Any = param.annotation
        if annotation is inspect.Parameter.empty:
            return None
        if isinstance(annotation, str):
            namespace = dict(func.__globals__)
            if func.__closure__:
                for name, cell in zip(
                    func.__code__.co_freevars,
                    func.__closure__,
                    strict=False,
                ):
                    namespace[name] = cell.cell_contents
            try:
                # eval() resolves PEP 563 stringified annotations back to
                # their actual types. The namespace is scoped to the handler
                # function's own __globals__ and closure variables, so only
                # names visible to the handler author can be resolved — no
                # untrusted input ever reaches this call.  The noqa suppression
                # is intentional; this mirrors typing.get_type_hints() internals.
                annotation = eval(annotation, namespace)  # noqa: S307
            except Exception:
                annotation = None
        if annotation is None:
            try:
                hints = get_type_hints(func, globalns=func.__globals__)
                annotation = hints.get(param.name)
            except (NameError, TypeError):
                return None
        if annotation is None:
            return None
        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            return annotation
        return None
