# SocketSpec — SYSTEM.md
**Version:** v0.1.0
**Author:** Laiba Shahab
**Last updated:** Initial release
**Location in repo:** `.context/v0.1.0/SYSTEM.md`

> This file is the complete system understanding for SocketSpec v0.1.0.
> Any AI tool, contributor, or developer picking up this project reads this file first.
> It describes what exists, how it connects, what flows through it, and what rules must never be broken.
> Do not make changes to the codebase that violate the invariants in this file without updating it first.

---

## 1. System Overview

SocketSpec is a Python WebSocket framework that provides FastAPI-style developer experience for real-time applications. It owns three things:

**1. A WebSocket event framework** — developers define socket event handlers using `@socket.on()` decorators with Pydantic-validated payloads, exactly like defining FastAPI routes.

**2. Framework adapters** — thin mounting layers for FastAPI, Starlette, Django, and Quart that translate each framework's WebSocket interface into SocketSpec's internal `Connection` object. A single function call mounts the entire socket app.

**3. A built-in docs and test UI** — served at `/socket-docs`, auto-generated from the event registry at runtime. Shows all events, payload schemas, and emits/broadcasts metadata. Has a live WebSocket test panel. No frontend required to develop or test socket events.

SocketSpec sits on top of the `websockets` / `anyio` transport layer. It does not implement the WebSocket protocol (RFC 6455). It owns everything above the transport: event routing, connection management, room management, session lifecycle, security layers, and documentation generation.

---

## 2. Core Invariants

These are the rules the system is built on. Any change that violates them breaks the design.

**INV-1: ConnectionManager is the single owner of connection state.**
No other module stores `Connection` objects or connection metadata directly. All reads and writes go through `ConnectionManager`. Enforced by: `ConnectionManager._lock` on all mutations.

**INV-2: The EventRegistry is the single source of truth for all socket events.**
Every event that exists in the system is registered here at startup. The docs engine reads from here. The router reads from here. Nothing else determines what events exist.

**INV-3: Startup validation runs before the server accepts any connection.**
`SocketApp._startup_validate()` is called by the framework adapter's `on_startup` hook. If validation fails (duplicate events, reserved names), the server raises and never starts. No invalid state at runtime.

**INV-4: Handler errors never kill the connection.**
All exceptions from user handler code are caught by `EventRouter._run_handler()`, formatted into the `__error__` envelope, emitted to the client, and logged. The WebSocket connection remains open. Only system-level failures (socket closed, auth expired) close the connection.

**INV-5: emits and broadcasts on @socket.on() are documentation metadata only.**
They never control handler behaviour. The handler body is the single source of truth for what actually happens. The registry uses these lists only to populate the docs UI event cards.

**INV-6: Security layers run in fixed order before any user code.**
Origin → Auth → Payload size → Pydantic → Rate limit → Middleware → DI → Handler.
No layer can be bypassed. The docs UI test panel goes through the exact same stack as a real client.

**INV-7: All state mutations are protected by asyncio.Lock.**
`ConnectionManager`, `MemoryBackend`, `TokenBucket`, and `RoomManager` all acquire their respective locks before modifying state. This prevents race conditions when multiple events arrive simultaneously.

**INV-8: No circular imports.**
The dependency direction is strictly: `errors` → `types` → `connection` → `backends` → `registry` → `session` → `security` → `middleware` → `di` → `router` → `manager` → `rooms` → `app` → `adapters` → `docs`. Nothing flows backward.

---

## 3. Module Map

Every file in `src/socketspec/`. Purpose, public API, and what it does NOT own.

---

### `_version.py`
**Purpose:** Single source of version string.
**Public API:** `__version__: str`
**Does NOT own:** Anything else. Import only in `__init__.py` and `pyproject.toml`.

---

### `errors.py`
**Purpose:** All custom exception classes and system constants (reserved event names, error codes).
**Public API:**
- `SocketSpecError` — base exception
- `DuplicateEventError` — startup: two handlers for same event name
- `ReservedEventNameError` — startup: user tries to register system event
- `ConnectionNotFoundError` — send to non-existent connection
- `RoomNotFoundError` — broadcast to non-existent room
- `AuthenticationError` — auth failed at connect
- `PayloadTooLargeError` — payload exceeds max_payload_size
- `RoomPermissionError` — room guard returned False
- `StartupValidationError` — general startup failure
- `RESERVED_EVENTS: frozenset[str]` — all system event names
- `ERROR_CODES: frozenset[str]` — all error code strings

**Does NOT own:** Any logic. Pure exception definitions and constants only.

---

### `types.py`
**Purpose:** Shared type aliases used across modules.
**Public API:**
- `EventName = str`
- `ConnectionId = str`
- `RoomName = str`
- `Namespace = str`
- `HandlerFunc = Callable[..., Awaitable[None]]`
- `PayloadDict = dict[str, Any]`
- `MiddlewareFunc = Callable[[Connection, EventName, PayloadDict, Callable], Awaitable[None]]`

**Does NOT own:** Any logic. Type aliases only. No imports from other socketspec modules (to keep it dependency-free).

---

### `connection.py`
**Purpose:** Data models for a live WebSocket connection and its identity.
**Public API:**
- `Identity(user_id, scopes, claims, raw_token, token_expires_at)` — auth result
- `SessionInfo(started_at, expires_at, token_expires_at)` — TTL metadata
- `Connection(id, raw_socket, identity, session, connected_at, last_active, rooms, metadata, headers, query_params, namespace)` — the object every handler receives
  - `conn.emit(event, payload)` — injected by `ConnectionManager` at connect time
  - `conn.disconnect(reason)` — injected by `ConnectionManager` at connect time

**Does NOT own:** Send logic (injected), auth logic, room management, session management.
**Key detail:** `Connection` is a pure dataclass. `emit` and `disconnect` are injected as bound callables by `ConnectionManager.connect()` to avoid circular imports.

---

### `registry.py`
**Purpose:** Stores and validates all registered event definitions.
**Public API:**
- `Emits(event, model, description)` — metadata for docs: what handler may emit to sender
- `Broadcasts(event, room, model, description)` — metadata for docs: what handler may broadcast
- `EventDefinition(name, namespace, handler, payload_model, emits, broadcasts, dependencies, description, tags, ordered, executor, deprecated)` — one registered event
- `EventRegistry`
  - `.register(definition)` → validates + stores
  - `.get(namespace, name)` → `EventDefinition | None`
  - `.all()` → `list[EventDefinition]`
  - `.validate()` → runs startup checks, raises `StartupValidationError` on failure

**Does NOT own:** Routing, dispatch, or handler execution. Read-write at registration, read-only at runtime.

---

### `backends/base.py`
**Purpose:** Protocol definition for all storage backends.
**Public API:**
- `BackendAdapter(Protocol)` — all methods that any backend must implement
  - `store_connection`, `remove_connection`, `connection_exists`
  - `get_room_members`, `add_to_room`, `remove_from_room`, `get_connection_rooms`
  - `publish`, `subscribe`, `unsubscribe`
  - `close`

**Does NOT own:** Any implementation. Protocol only.

---

### `backends/memory.py`
**Purpose:** In-process backend. Default. Single-process deployments.
**Public API:** `MemoryBackend` — implements `BackendAdapter`
**Key detail:** All mutations protected by a single `asyncio.Lock`. In-memory pub/sub delivers directly to subscribers in the same process. No network calls.

**Does NOT own:** Cross-process communication (that is Redis). Connection objects (that is `ConnectionManager`).

---

### `session.py`
**Purpose:** Session configuration and per-connection TTL enforcement.
**Public API:**
- `SessionConfig(max_duration, idle_timeout, heartbeat_interval, heartbeat_timeout, token_refresh_window, redis_key_ttl)`
- `SessionManager`
  - `.start(conn)` — launches heartbeat + idle + max_duration tasks for one connection
  - `.stop(conn_id)` — cancels all tasks for one connection on disconnect
  - `.touch(conn)` — updates `conn.last_active` on every incoming event

**Does NOT own:** Connection state (that is `ConnectionManager`). Auth refresh logic (triggers event, user handles it).

---

### `security/origins.py`
**Purpose:** Origin header validation at HTTP upgrade handshake.
**Public API:**
- `OriginValidator(allowed_origins: list[str])`
  - `.is_allowed(origin: str | None) → bool`

**Key detail:** `"*"` in `allowed_origins` allows all origins (dev mode). `None` origin header always rejected in production mode.

---

### `security/ratelimit.py`
**Purpose:** Per-connection event rate limiting using token bucket algorithm.
**Public API:**
- `RateLimit(events, per_seconds)` — config dataclass
- `TokenBucket(config: RateLimit)`
  - `.consume(conn_id) → bool` — True if allowed, False if limited
  - `.remove(conn_id)` — clean up on disconnect

**Key detail:** Token bucket refills continuously over time, not on fixed windows. More fair than fixed-window rate limiting.

---

### `security/auth.py`
**Purpose:** Authentication protocol and built-in implementations.
**Public API:**
- `AuthBackend(Protocol)` — `.authenticate(headers, query_params) → Identity | None`
- `JWTAuth(secret, algorithm, header)` — validates JWT from Authorization header or `?token=` query param
- `APIKeyAuth(api_key, header)` — validates API key from header or `?api_key=` query param

**Does NOT own:** Session management, token refresh logic. Only: can this connection authenticate? Yes → Identity. No → None.

---

### `middleware.py`
**Purpose:** Builds and executes the middleware chain.
**Public API:**
- `MiddlewareChain(middlewares: list[MiddlewareFunc])`
  - `.compile(final_handler: Callable) → Callable` — returns single callable that runs full chain

**Key detail:** Chain is compiled once at startup, not rebuilt per event. Order is FIFO (first registered runs first). Each middleware calls `await call_next()` to proceed.

---

### `di.py`
**Purpose:** FastAPI-style dependency injection resolver.
**Public API:**
- `Depends(dependency: Callable)` — marks a parameter for injection
- `DependencyResolver`
  - `.resolve(handler, conn) → dict[str, Any]` — resolves all `Depends()` in handler signature

**Key detail:** Supports chained dependencies (A depends on B which depends on C). Supports `yield`-based dependencies for cleanup (like `get_db()`). Resolved before handler runs, cleanup runs after handler completes.

---

### `router.py`
**Purpose:** Routes incoming events to the correct handler after all security layers pass.
**Public API:**
- `EventRouter(registry, di_resolver)`
  - `.dispatch(conn, event, payload)` — looks up handler, validates payload, runs handler
  - `.cleanup(conn_id)` — removes per-connection ordered queue on disconnect

**Key detail:** Non-ordered events run as `asyncio.create_task()` — fully isolated. Ordered events (`ordered=True`) queue per-connection and run sequentially. Handler exceptions are caught here, formatted into `__error__`, and emitted to client.

---

### `manager.py`
**Purpose:** Owns all live WebSocket connections.
**Public API:**
- `ConnectionManager(backend: BackendAdapter)`
  - `.connect(conn)` — registers connection, injects `emit` and `disconnect` into `conn`
  - `.disconnect(conn)` — removes connection, cleans up backend
  - `.get(conn_id) → Connection | None`
  - `.all() → list[Connection]`
  - `.send(conn_id, event, payload)` — delivers message to one connection

**Does NOT own:** Auth, rate limiting, session management, rooms. Only: which connections exist and how to send to them.

---

### `rooms.py`
**Purpose:** Room creation, membership, and broadcasting.
**Public API:**
- `Room(name, private, max_members, ttl, metadata)` — room configuration
- `RoomManager(backend, manager)`
  - `.join(conn, room)` — adds connection to room, runs guard if pattern matches
  - `.leave(conn, room)` — removes connection from room
  - `.broadcast(room, event, payload)` — sends to all room members in chunks
  - `.broadcast_all(event, payload)` — sends to every connected client
  - `.broadcast_except(exclude_id, event, payload)` — sends to all except one
  - `.members(room) → list[Connection]`
  - `.register_guard(pattern, guard)` — registers a room permission function
  - `.register_static(room)` — registers a room that always exists

**Key detail:** Broadcasts are chunked at `BROADCAST_CHUNK_SIZE = 500`. Each chunk uses `asyncio.gather`. Per-connection `try/except` inside gather — one dead connection never stops the broadcast.

---

### `app.py`
**Purpose:** The main `SocketApp` class. Entry point for all user code.
**Public API:**
- `SocketApp(docs, docs_url, docs_access_token, auth, backend, allowed_origins, max_payload_size, rate_limit, session, rooms, namespace)`
  - `.on(event, *, description, tags, emits, broadcasts, ordered, executor, deprecated)` — decorator: register event handler
  - `.middleware(func)` — decorator: register middleware
  - `.on_connect(func)` — lifecycle hook decorator
  - `.on_disconnect(func)` — lifecycle hook decorator
  - `.on_error(func)` — lifecycle hook decorator
  - `.on_room_join(func)` — lifecycle hook decorator
  - `.on_room_leave(func)` — lifecycle hook decorator
  - `.room_guard(pattern)` — decorator: protect a room pattern
  - `.rooms` — `RoomManager` instance, available in handlers
  - `.handle_connect(raw_socket, headers, query_params) → Connection | None` — called by adapters
  - `.handle_event(conn, raw_message)` — called by adapters on each message
  - `.handle_disconnect(conn, reason)` — called by adapters on close
  - `._startup_validate()` — called by adapter's on_startup hook

**Does NOT own:** Raw WebSocket transport (adapters own that), authentication implementation (auth backends own that).

---

### `adapters/fastapi.py`
**Purpose:** Mounts SocketSpec into a FastAPI application.
**Public API:**
- `mount(socket_app, app, *, path="/ws")` — adds WebSocket endpoint + startup/shutdown hooks + docs routes

**Key detail:** `FastAPISocketWrapper` normalises FastAPI's `WebSocket` object to the interface `ConnectionManager.send()` expects (`send_json`, `close`). Adapter's only job: translate. No business logic here.

---

### `docs/engine.py`
**Purpose:** Reads EventRegistry and produces the JSON schema for the docs UI.
**Public API:**
- `DocsEngine(registry)`
  - `.generate_schema() → dict` — called once per page load, returns full event schema

**Key detail:** Schema is generated at request time, not at startup. This means it always reflects the current state of the registry (useful if dynamic registration is ever added).

---

### `docs/router.py`
**Purpose:** HTTP routes that serve the docs UI and schema.
**Public API:** (internal — mounted by `adapters/fastapi.py`)
- `GET /socket-docs` → serves `docs/ui/index.html`
- `GET /socket-docs/schema` → returns `DocsEngine.generate_schema()` as JSON

**Key detail:** If `docs_access_token` is set, all docs routes check for `Authorization: Bearer <token>` or `?token=` before serving. Returns 401 without token. This is separate from the WebSocket auth — it protects the docs page itself.

---

### `testing.py`
**Purpose:** In-process TestClient for automated tests. No running server needed.
**Public API:**
- `TestClient(app, *, auth_token)`
  - `.connect(*, query_params) → AsyncContextManager[TestConnection]`
- `TestConnection`
  - `.emit(event, payload)` — send event to app
  - `.receive(event, *, timeout) → dict` — wait for specific event
  - `.receive_broadcast(event, room, *, timeout) → dict` — wait for broadcast
  - `.join_room(room)` — utility: emit join and confirm

**Key detail:** Uses `anyio` memory streams to simulate WebSocket connection without network. Goes through the full `SocketApp` stack — same security, same middleware, same handlers as a real connection.

---

## 4. Data Flows

Step-by-step trace of every major operation through the system.

### 4.1 Client Connect

```
Browser opens WebSocket to ws://host/ws
         ↓
[Adapter] HTTP upgrade request intercepted
         ↓
[Adapter] Origin header checked via OriginValidator
         ↓ REJECT (403) if origin not allowed
         ↓ ACCEPT → WebSocket established
         ↓
[SocketApp.handle_connect()]
         ↓
[AuthBackend.authenticate()] called if auth configured
         ↓ returns None → send __error__ AUTH_ERROR, close ws
         ↓ returns Identity → continue
         ↓
Connection object built (UUID4 id, Identity, headers, query_params)
         ↓
[ConnectionManager.connect(conn)]
  ├── asyncio.Lock acquired
  ├── conn stored in _connections[conn.id]
  ├── backend.store_connection() called
  ├── conn.emit injected as bound callable
  ├── conn.disconnect injected as bound callable
  └── lock released
         ↓
[SessionManager.start(conn)] — heartbeat task launched
         ↓
on_connect hooks run (user-defined)
         ↓
Connection ready — adapter enters message receive loop
```

### 4.2 Client Sends Event

```
Client sends: {"event": "send_message", "payload": {"room": "lobby", "text": "hi"}}
         ↓
[Adapter] receives raw text frame
         ↓
[SocketApp.handle_event(conn, raw_message)]
         ↓
Payload size check: len(raw_message) > max_payload_size?
         ↓ YES → conn.emit("__error__", {code: "PAYLOAD_TOO_LARGE"}), return
         ↓ NO → continue
         ↓
JSON parse: extract event name + payload dict
         ↓ ParseError → conn.emit("__error__", {code: "VALIDATION_ERROR"}), return
         ↓
[TokenBucket.consume(conn.id)] if rate_limit configured
         ↓ False → conn.emit("__error__", {code: "RATE_LIMIT_ERROR"}), return
         ↓ True → continue
         ↓
[SessionManager.touch(conn)] — update last_active
         ↓
[compiled_middleware_chain(conn, event, payload)]
         ↓
[EventRouter.dispatch(conn, event, payload)]
         ↓
Registry lookup: registry.get(conn.namespace, event)
         ↓ None → conn.emit("__error__", {code: "UNKNOWN_EVENT"}), return
         ↓ EventDefinition found → continue
         ↓
Pydantic validate payload against definition.payload_model
         ↓ ValidationError → conn.emit("__error__", {code: "VALIDATION_ERROR", details}), return
         ↓ valid → continue
         ↓
ordered=True?
  ├── YES → put (definition, payload) in conn's asyncio.Queue
  │          queue processor runs handler sequentially
  └── NO  → asyncio.create_task(_run_handler(conn, definition, payload))
         ↓
[DependencyResolver.resolve(handler, conn)] → injected dict
         ↓
await handler(conn, validated_payload, **injected)
         ↓ Exception → caught, conn.emit("__error__", {code: "HANDLER_ERROR"}), logged
         ↓ Success → handler emits/broadcasts/joins rooms as its logic dictates
```

### 4.3 Handler Broadcasts to a Room

```
Inside handler:
await socket.rooms.broadcast("chat:lobby", "new_message", payload)
         ↓
[RoomManager.broadcast("chat:lobby", "new_message", payload)]
         ↓
[backend.get_room_members("chat:lobby")] → list of connection_ids
         ↓
chunk member_ids into groups of BROADCAST_CHUNK_SIZE (500)
         ↓
For each chunk:
  asyncio.gather(*[_safe_send(conn_id, "new_message", payload) for conn_id in chunk])
         ↓
[_safe_send(conn_id, event, payload)]:
  try:
    await manager.send(conn_id, event, payload)
  except Exception:
    logger.debug("Dead connection %s skipped", conn_id)  # silent, never raises
         ↓
[ConnectionManager.send(conn_id, event, payload)]:
  conn = _connections.get(conn_id)
  if conn is None: return  # already gone
  await conn.raw_socket.send_json({"event": event, "payload": payload})
```

### 4.4 Client Disconnect

```
Browser closes WebSocket (or TCP drops)
         ↓
[Adapter] receives WebSocketDisconnect exception from recv loop
         ↓
[SocketApp.handle_disconnect(conn, reason="client_close")]
         ↓
[SessionManager.stop(conn.id)] — cancels heartbeat, idle, max_duration tasks
         ↓
For each room in conn.rooms:
  [RoomManager.leave(conn, room)]
    ├── backend.remove_from_room(conn.id, room)
    └── conn.rooms.discard(room)
  on_room_leave hooks run
         ↓
[ConnectionManager.disconnect(conn)]
  ├── asyncio.Lock acquired
  ├── _connections.pop(conn.id)
  ├── backend.remove_connection(conn.id)
  └── lock released
         ↓
on_disconnect hooks run
         ↓
[TokenBucket.remove(conn.id)] if rate_limit configured
         ↓
[EventRouter.cleanup(conn.id)] — removes ordered queue if exists
         ↓
Connection fully cleaned up — no state remains
```

### 4.5 Error Emitted to Client

```
Any layer raises or detects an error condition
         ↓
[EventRouter._emit_error(conn, code, event, message, details)]
  OR [SocketApp.handle_event() early returns with error]
         ↓
payload = {
    "event": "__error__",
    "payload": {
        "code": code,           # machine-readable
        "event": event,         # which event caused it
        "message": message,     # human-readable
        "request_id": uuid4(),  # traceable in logs
        "details": details,     # Pydantic errors or {}
    }
}
         ↓
await conn.emit("__error__", payload["payload"])
         ↓
Connection stays open (unless error was AUTH_ERROR at connect time)
         ↓
Frontend: socket.on("__error__", handler) receives it
```

---

## 5. Dependency Graph

Who imports who. Read left to right = "imports from".

```
errors          → (nothing in socketspec)
types           → (nothing in socketspec)
connection      → types, errors
backends/base   → types
backends/memory → types, errors, backends/base
session         → connection, errors
security/origins→ (nothing in socketspec)
security/ratelimit → types
security/auth   → connection
middleware      → connection, types
di              → connection
registry        → errors, connection
router          → registry, di, connection, types, errors
manager         → connection, types, backends/base, errors
rooms           → connection, types, backends/base, errors, manager
app             → ALL of the above (orchestrator)
adapters/*      → app, connection (thin wrappers only)
docs/engine     → registry, _version
docs/router     → docs/engine
testing         → app, connection, types
__init__        → everything (re-exports public API)
```

No arrows point backward (no circular imports). This graph is enforced by the build order in the implementation plan.

---

## 6. Active Decisions

Decisions made in v0.1.0 that future versions must respect unless explicitly reversed.

**DEC-01: Own the abstraction, not a wrapper.**
SocketSpec does not wrap Socket.IO or python-socketio. It owns everything above the raw WebSocket transport. Rationale: wrapping gives inherited limitations and prevents owning the developer experience.

**DEC-02: emits/broadcasts are metadata only.**
They never control handler behaviour. Handler body is the single source of truth. Rationale: conditional logic cannot be expressed in decorators.

**DEC-03: Async-only core.**
No sync support in v0.1.0. `SyncSocketApp` is a planned community contribution. Rationale: sync+async in one codebase adds complexity before the core is proven.

**DEC-04: Handler errors never kill the connection.**
All user handler exceptions are caught by `EventRouter`, formatted as `__error__`, and emitted to the client. The connection stays open. Rationale: a bug in one handler should not disconnect the user.

**DEC-05: Broadcast chunks at 500.**
`BROADCAST_CHUNK_SIZE = 500` in `rooms.py`. `asyncio.gather(50000 coroutines)` causes memory spikes. Chunking prevents this. Value is configurable as a constant, not a user-facing config option in v0.1.0.

**DEC-06: Per-connection `try/except` in broadcasts.**
Each `_safe_send` call is individually wrapped. One dead connection never stops the broadcast to the remaining members. Rationale: network failures on individual connections are expected and should be handled silently.

**DEC-07: Middleware chain compiled once at startup.**
`MiddlewareChain.compile()` builds the call chain once. Zero per-event overhead beyond actual function calls. Rationale: performance — middleware cannot change at runtime.

**DEC-08: Single-client docs UI in v0.1.0.**
The docs UI serves one authenticated WebSocket connection per tab. Multiple clients are tested by opening multiple browser tabs. Rationale: multi-client panel is genuinely useful but adds significant UI complexity. It is deferred to v0.4.0.

**DEC-09: Apache 2.0 license.**
Chosen over MIT for patent protection and enforced attribution. Contributor License Agreement (CLA) via CLA Assistant required on all PRs. Rationale: Laiba Shahab retains IP ownership of the complete project.

---

## 7. Known Limitations in v0.1.0

These are intentional constraints, not bugs. Documented so contributors know what is and is not in scope.

- **Single-process only.** Redis backend is v0.3.0. Multi-server broadcasting not yet supported.
- **JSON payloads only.** Binary WebSocket frames are v0.3.0.
- **Memory backend only.** No persistence. All state lost on restart.
- **Single client in docs UI.** Multi-client panel is v0.4.0. Use multiple tabs.
- **No sync support.** Async only. Sync adapter is a community contribution milestone.
- **FastAPI adapter only.** Starlette, Django, Quart adapters are v0.2.0.
- **DI support — Phase 2.** `Depends()` resolution is planned for v0.2.0. In v0.1.0, handlers receive `conn` and `payload` only.
- **No metrics or tracing.** Prometheus and OpenTelemetry are v0.4.0.
- **No graceful shutdown.** SIGTERM handling is v0.3.0.

---

## 8. File Checklist for v0.1.0

Every file that must exist before v0.1.0 is tagged.

**Source:**
- [ ] `src/socketspec/__init__.py`
- [ ] `src/socketspec/_version.py`
- [ ] `src/socketspec/errors.py`
- [ ] `src/socketspec/types.py`
- [ ] `src/socketspec/connection.py`
- [ ] `src/socketspec/registry.py`
- [ ] `src/socketspec/session.py`
- [ ] `src/socketspec/middleware.py`
- [ ] `src/socketspec/router.py`
- [ ] `src/socketspec/manager.py`
- [ ] `src/socketspec/rooms.py`
- [ ] `src/socketspec/app.py`
- [ ] `src/socketspec/testing.py`
- [ ] `src/socketspec/backends/__init__.py`
- [ ] `src/socketspec/backends/base.py`
- [ ] `src/socketspec/backends/memory.py`
- [ ] `src/socketspec/security/__init__.py`
- [ ] `src/socketspec/security/origins.py`
- [ ] `src/socketspec/security/ratelimit.py`
- [ ] `src/socketspec/security/auth.py`
- [ ] `src/socketspec/adapters/__init__.py`
- [ ] `src/socketspec/adapters/fastapi.py`
- [ ] `src/socketspec/docs/__init__.py`
- [ ] `src/socketspec/docs/engine.py`
- [ ] `src/socketspec/docs/router.py`
- [ ] `src/socketspec/docs/ui/index.html`
- [ ] `src/socketspec/docs/ui/main.js`
- [ ] `src/socketspec/docs/ui/style.css`

**Tests:**
- [ ] `tests/conftest.py`
- [ ] `tests/unit/test_registry.py`
- [ ] `tests/unit/test_manager.py`
- [ ] `tests/unit/test_rooms.py`
- [ ] `tests/unit/test_session.py`
- [ ] `tests/unit/test_middleware.py`
- [ ] `tests/unit/test_errors.py`
- [ ] `tests/unit/backends/test_memory.py`
- [ ] `tests/unit/security/test_auth.py`
- [ ] `tests/unit/security/test_origins.py`
- [ ] `tests/unit/security/test_ratelimit.py`
- [ ] `tests/integration/test_event_flow.py`
- [ ] `tests/integration/test_rooms.py`
- [ ] `tests/integration/test_error_handling.py`
- [ ] `tests/adapters/test_fastapi_adapter.py`

**Repo root:**
- [ ] `pyproject.toml`
- [ ] `README.md`
- [ ] `CONTRIBUTING.md`
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `CHANGELOG.md`
- [ ] `SECURITY.md`
- [ ] `ROADMAP.md`
- [ ] `AUTHORS`
- [ ] `NOTICE`
- [ ] `CLA.md`
- [ ] `LICENSE` (Apache 2.0 full text)
- [ ] `.pre-commit-config.yaml`
- [ ] `.gitignore`
- [ ] `.context/CODING_STANDARDS.md`
- [ ] `.context/SYSTEM_CURRENT.md` (copy of this file)
- [ ] `.context/v0.1.0/SYSTEM.md` (this file)

---

## 9. How to Update This File

When making changes that affect the system structure:

1. Update the relevant section in `.context/SYSTEM_CURRENT.md`
2. Add an entry under the relevant section header with what changed and why
3. If the change introduces a new invariant, add it to Section 2
4. If the change adds a module, add it to Section 3
5. If the change alters a data flow, update Section 4
6. If the change makes a technical decision, add it to Section 6
7. On version release: copy `SYSTEM_CURRENT.md` to `.context/vX.Y.Z/SYSTEM.md`

This file is the ground truth. The code implements it. Not the other way around.
