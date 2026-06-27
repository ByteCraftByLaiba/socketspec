# SocketSpec — Complete Project Context

> Everything we analyzed, decided, and designed.  
> From problem to solution to architecture to community.  
> This is the single source of truth before a line of code is written.

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [The Solution](#2-the-solution)
3. [Core Philosophy](#3-core-philosophy)
4. [What We Are Building — Three Things](#4-what-we-are-building--three-things)
5. [Framework & Server Compatibility](#5-framework--server-compatibility)
6. [Technical Decisions](#6-technical-decisions)
7. [Architecture — All Layers](#7-architecture--all-layers)
8. [Event System — Directions & Contracts](#8-event-system--directions--contracts)
9. [Room Management](#9-room-management)
10. [Docs UI](#10-docs-ui)
11. [Security Model](#11-security-model)
12. [Session Management & TTL](#12-session-management--ttl)
13. [Customization — What System Handles vs User](#13-customization--what-system-handles-vs-user)
14. [Edge Cases & Critical Scenarios](#14-edge-cases--critical-scenarios)
15. [Python Module Standards](#15-python-module-standards)
16. [GitHub & Community Setup](#16-github--community-setup)
17. [Open Source Strategy](#17-open-source-strategy)
18. [Build Roadmap](#18-build-roadmap)

---

## 1. The Problem

### Where This Started

Across many real-time production systems — tracking platforms, AI applications, communication tools, collaboration software — all built on modern Python backends, the developer pain is identical regardless of the domain:

- You write socket event handlers on the backend
- You **cannot test them** until a frontend is connected
- You build a throwaway HTML file to test, then rebuild it every time an event or payload changes
- In agile projects you lose track of which events exist, what payloads they expect, and what they return
- There is no source of truth for the socket contract in the codebase
- No one on the team — including the frontend — has a clear view of what events exist

### The Root Cause

HTTP solved developer experience with OpenAPI + Swagger. REST routes are registered explicitly, so the framework knows about every route at startup. Documentation and testing are natural byproducts.

WebSocket events are handled implicitly via decorators and callbacks. There is no central registry the framework exposes. The developer has to build and maintain that registry manually, or it just doesn't exist.

**AsyncAPI exists as a spec, but no one has built the FastAPI-equivalent developer experience around it** — auto-discovery of events + live test UI in a single package.

### Who Feels This Pain

- Developers building **logistics and tracking systems** — order status, fleet tracking, shipment updates
- Developers building **AI applications** — LLM token streaming, agent status, inference pipelines
- Developers building **communication platforms** — chat, customer support, team messaging
- Developers building **collaborative tools** — shared documents, whiteboards, multiplayer features
- Developers building **financial platforms** — live price feeds, trading dashboards, portfolio updates
- Developers building **healthcare systems** — patient monitoring, alert systems, live diagnostics
- Developers building **IoT dashboards** — device telemetry, sensor feeds, remote control
- Developers building **gaming backends** — game state sync, matchmaking, leaderboards
- Developers building **media and streaming platforms** — live comments, viewer counts, reactions
- Developers building **DevOps tooling** — build logs, deployment status, pipeline monitoring
- **Frontend developers** who need to know exactly what to emit and what to listen for
- **QA engineers** who need to test real-time behavior without a full frontend setup

This is not a niche problem. It is a universal pain for anyone doing WebSockets in Python.

---

## 2. The Solution

A Python package that makes WebSocket development feel exactly like FastAPI development.

- **Write socket event handlers the same way you write FastAPI routes** — decorators, Pydantic models, type hints
- **Mount into any framework in one line** — FastAPI, Django, Starlette, Flask (async), and others
- **Get a built-in Swagger-equivalent docs UI** served at `/socket-docs` — always live, always accurate, fully testable in browser
- **No frontend required at any point** to develop, test, or document socket behavior

The core insight: **by owning the abstraction layer, documentation and testing become natural byproducts, not plugins bolted onto someone else's system.**

---

## 3. Core Philosophy

These are the non-negotiable principles that drive every decision.

### Abstraction is the key

The developer should never deal with raw WebSocket frames, connection lifecycle, heartbeats, race conditions, or room state management. These are infrastructure concerns. The framework owns them completely.

### No added overhead

Every feature in the framework must justify its existence. No complexity is added unless it solves a real, recurring problem. The goal is to remove overhead from the developer's app, never to add it.

### Security is not optional

Security is layered into the system architecture, not something a developer opts into. Origin validation, payload size limits, rate limiting, and auth hooks exist by default. The defaults are safe. Developers configure them, they do not implement them.

### Reliable enough for production

The framework must be trustworthy across the full spectrum of real-time applications — high-throughput event systems, long-lived streaming connections, broadcast-heavy platforms, and ordering-sensitive workflows. Any of these use cases defines the reliability bar, not just one.

### More contributions = reliable community = trust

Open source trust is earned through code quality, clear architecture, good documentation, and a welcoming contributor experience. The codebase is designed to be readable and approachable. Every layer is a potential contribution point.

---

## 4. What We Are Building — Three Things

**1. A WebSocket Framework (the core)**

A `SocketApp` class that provides a clean, FastAPI-style API for defining socket event handlers. Pydantic validation built in. Event routing, connection management, room management — all handled by the framework.

**2. Framework Adapters**

Thin mounting layers for FastAPI, Starlette, Django (ASGI), Litestar, Sanic, Quart, and eventually Flask. Each adapter translates the framework's WebSocket interface into the framework's `Connection` object. Single function call to mount.

**3. Docs + Test UI (the differentiator)**

A browser-based interface served at `/socket-docs`. Auto-generated from the event registry at runtime. Shows all events, directions, payload schemas, room relationships. Has a live WebSocket connection to your server. Click any event, fill in the payload, fire it, see the response. No frontend required.

---

## 5. Framework & Server Compatibility

### ASGI Frameworks — Primary Targets

| Framework | Priority | Notes |
|---|---|---|
| FastAPI | Day 1 | Largest async Python audience, built on Starlette |
| Starlette | Day 1 | FastAPI sits on it — near-free adapter |
| Django (ASGI mode 3.1+) | Day 1 | 44% of Python web developers |
| Litestar | Milestone 2 | Growing fast, modern API crowd |
| Sanic | Milestone 2 | High-performance niche |
| Quart | Milestone 3 | Flask users migrating to async |
| Django Channels | Milestone 3 | Existing Django WebSocket users |

### WSGI Frameworks — Sync Milestone

| Framework | Priority | Notes |
|---|---|---|
| Flask | Contributor milestone | Needs sync adapter, architecture supports it |
| Django (WSGI) | Contributor milestone | Sync adapter on top of async core |

### ASGI Servers — All Supported Automatically

Because the framework exposes a standard ASGI app, it runs on all ASGI servers without any adapter work:

- **Uvicorn** — primary, standard for FastAPI/Starlette
- **Hypercorn** — HTTP/3 and QUIC support
- **Daphne** — Django Channels standard
- **Granian** — Rust-based, high-performance option
- **Gunicorn + UvicornWorker** — production standard

No server-specific code. No configuration. The ASGI spec handles it.

---

## 6. Technical Decisions

### Decision 1: Own the abstraction, not a wrapper

**Rejected:** Wrapping Socket.IO or python-socketio.

**Reason:** Socket.IO adds HTTP long-polling fallback (unnecessary in 2026), its own wire protocol (clients need a Socket.IO client, not a standard WebSocket client), and its complexity becomes inherited complexity. Wrapping someone else's system means you can never fully own the developer experience.

**Decision:** Own everything above the raw WebSocket transport layer.

### Decision 2: Raw WebSocket transport via `websockets` library

**Rejected:** Implementing RFC 6455 (WebSocket protocol) from scratch.

**Reason:** Not worth it. That's bytes and frames, not developer experience.

**Decision:** Use Python's `websockets` or `anyio` library for the raw transport only. Own the event system, routing, validation, connection management, rooms, docs — everything above the transport.

### Decision 3: Async-only core

**Rejected:** Sync + async simultaneously from day one.

**Reason:** Sync and async in the same codebase creates `asyncio.run()` hacks everywhere and doubles testing surface before the core idea is even proven.

**Decision:** Pure async core (Python 3.10+). The architecture leaves a clean door open for sync support as a community contribution. `SyncSocketApp` can subclass `SocketApp` and run the async core in an event loop. Documented explicitly in `CONTRIBUTING.md` as a planned milestone.

### Decision 4: Pydantic for all payload validation

**Reason:** The Python async developer community already knows Pydantic. It handles schema inference, JSON Schema generation, and error formatting. This means the docs UI gets schemas for free — same way FastAPI gets OpenAPI schemas for free.

### Decision 5: Memory backend default, Redis backend as swap

**Reason:** Memory backend works for single-process development and small deployments with zero config. Redis backend is one line to enable and handles multi-server deployments via pub/sub. The user never changes application code, only the backend config.

### Decision 6: Metadata-only direction declarations inside @socket.on()

**Rejected:** Stacked decorators (`@socket.emits()`, `@socket.broadcasts()`) that control behavior.

**Reason:** In real code, emitting, broadcasting, and room joining are conditional outcomes of one piece of logic. They are not separate concerns. A decorator cannot capture conditional branching — if the decorator controls the actual broadcast, conditional cases break. Stacked decorators also become unreadable as handlers grow.

**Rejected:**
```python
# Unreadable, can't handle conditional logic
@socket.on("update_order")
@socket.emits("order_ack", model=OrderAckPayload)
@socket.broadcasts("order_changed", room="order:{id}", model=OrderChangedPayload)
async def update_order(conn, payload): ...
```

**Decision:** `emits` and `broadcasts` are metadata parameters inside `@socket.on()` — they describe what a handler *can* emit or broadcast, purely for the docs registry. They never control behavior. The handler body is always the single source of truth for logic.

```python
@socket.on(
    "update_order",
    description="Update an order's status",
    tags=["orders"],
    emits=[
        Emits("order_ack", model=OrderAckPayload, description="Confirms the update result")
    ],
    broadcasts=[
        Broadcasts("order_changed", room="order:{order_id}", model=OrderChangedPayload)
    ]
)
async def update_order(conn: Connection, payload: OrderPayload):
    result = await db.update_order(payload.order_id, payload.status)
    if result.success:
        await socket.rooms.join(conn, f"order:{payload.order_id}")
        await conn.emit("order_ack", OrderAckPayload(success=True))
        await socket.rooms.broadcast(
            f"order:{payload.order_id}", "order_changed", OrderChangedPayload(**result.data)
        )
    else:
        await conn.emit("order_ack", OrderAckPayload(success=False, error=result.error))
        # No broadcast on failure — conditional logic fully owned by handler
```

The docs engine reads `emits` and `broadcasts` from the registry to render the frontend contract. The handler body does whatever the business logic requires.

### Decision 7: Dependency Injection via Depends()

**Decision:** Support FastAPI-style `Depends()` injection in handlers. Phase 2, not Phase 1.

**Reason:** FastAPI developers already have muscle memory for `Depends()`. Auth, DB sessions, and service injection feel natural. At registration time, `inspect.signature()` scans the handler and records any `Depends(...)` parameters in the `EventDefinition`. At event time, the framework resolves the dependency tree and injects values before the handler runs. Existing handlers require no changes when DI is added — it hooks into function signatures.

```python
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

async def require_admin(conn: Connection, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get_user(conn.identity.user_id)
    if not user.is_admin:
        raise PermissionError("Admin required")
    return user

@socket.on("admin_action", tags=["admin"])
async def admin_action(
    conn: Connection,
    payload: AdminPayload,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    ...
```

---

## 7. Architecture — All Layers

```
┌──────────────────────────────────────────────────────────────────┐
│                         SocketApp                                │
│                                                                  │
│   EventRegistry  →  EventRouter  →  EventHandler                │
│                                                                  │
│   ConnectionManager  →  RoomManager                             │
│                                                                  │
│   BackendAdapter  (MemoryBackend | RedisBackend)                 │
└──────────────────────────────────────────────────────────────────┘
          ↕                                     ↕
   FrameworkAdapter                         DocsEngine
   FastAPI / Django /                       /socket-docs
   Starlette / Quart                        Swagger-style UI
```

### Layer 1 — EventRegistry

The single source of truth for all socket events. Every `@socket.on()` call writes here at import time. The docs engine reads from here. Nothing else owns event knowledge.

```python
@dataclass
class Emits:
    event: str
    model: type[BaseModel] | None
    description: str = ""

@dataclass
class Broadcasts:
    event: str
    room: str                        # supports patterns like "order:{order_id}"
    model: type[BaseModel] | None
    description: str = ""

@dataclass
class EventDefinition:
    name: str
    namespace: str
    handler: Callable
    payload_model: type[BaseModel] | None
    emits: list[Emits]               # metadata only — docs registry
    broadcasts: list[Broadcasts]     # metadata only — docs registry
    dependencies: list[Depends]      # DI chain resolved at event time
    description: str
    tags: list[str]
    deprecated: bool = False
    ordered: bool = False
    executor: bool = False
```

Startup validation runs on the full registry before the server accepts connections:
- Duplicate event names → `DuplicateEventError` at startup
- Reserved names (`__error__`, `__connect__`, etc.) → `ReservedEventNameError` at startup

Nothing fails silently at runtime that could have been caught at startup.

### Layer 2 — ConnectionManager

Single owner of all live connections. No handler ever touches connection state directly.

```python
class ConnectionManager:
    async def connect(self, conn: Connection) -> None
    async def disconnect(self, conn: Connection) -> None
    async def get(self, id: str) -> Connection | None
    async def all(self) -> list[Connection]
    async def send(self, id: str, event: str, payload: dict) -> None
```

Memory backend uses `asyncio.Lock` on every mutation.
Redis backend uses Redis locks on every mutation.
Race conditions are impossible by design — all state changes go through one class, one lock.

### Layer 3 — Event Flow (ordered, zero race conditions)

```
Client sends event
        ↓
Origin check         ← at HTTP upgrade handshake, WS not yet open
        ↓
ConnectionManager confirms connection is live
        ↓
Payload size check   ← raw bytes, before deserialization
        ↓
Pydantic validates   ← fails fast, clean error, never reaches handler
        ↓
Rate limiter         ← token bucket, per connection
        ↓
Middleware chain     ← compiled once at startup, zero per-event overhead
        ↓
Dependency injection ← Depends() tree resolved, values injected
        ↓
asyncio.create_task(handler(conn, payload, ...injected))   ← isolated task
        ↓                 ↓
   Task A runs        Task B runs    ← fully isolated, never block each other
```

Each handler is an independent `asyncio.Task`. Two clients firing the same event simultaneously get two completely isolated tasks. No shared mutable state between them.

### Layer 4 — BackendAdapter Protocol

```python
class BackendAdapter(Protocol):
    async def store_connection(self, id: str, meta: dict) -> None
    async def remove_connection(self, id: str) -> None
    async def get_room_members(self, room: str) -> list[str]
    async def add_to_room(self, id: str, room: str) -> None
    async def remove_from_room(self, id: str, room: str) -> None
    async def publish(self, channel: str, event: str, payload: dict) -> None
    async def subscribe(self, channel: str, callback: Callable) -> None
```

**MemoryBackend** — default. Single process. `asyncio.Lock` on all mutations.

**RedisBackend** — multi-process, multi-server. Redis pub/sub for broadcasting. Every server subscribes to relevant channels on startup. Broadcasting across 10 servers is invisible to application code.

```python
# Zero application code change
socket = SocketApp()                                            # memory
socket = SocketApp(backend="redis", url="redis://localhost")   # redis
```

### Layer 5 — Multi-Server Broadcast Model (Redis)

```
                       Redis Pub/Sub
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
      Server 1           Server 2           Server 3
      conn A,B,C         conn D,E           conn F
         │
   Client A fires "send_message" to room "chat:lobby"
         │
   Handler runs on Server 1
         │
   socket.rooms.broadcast("chat:lobby", ...)
         │
   Redis PUBLISH "room:chat:lobby" → payload
         │
         ├── Server 1 receives → delivers to A, B, C (local)
         ├── Server 2 receives → delivers to D (in room, local)
         └── Server 3 receives → delivers to F (in room, local)
```

Rules:
- WebSocket connections are always owned by one server
- Connection metadata (user, rooms joined) lives in Redis
- Actual delivery always happens locally on the server that owns the connection
- Redis is the message bus only, not the delivery mechanism
- Horizontal scaling is invisible to application code

### Layer 6 — RoomManager

```python
class RoomManager:
    async def join(self, conn: Connection, room: str) -> None
    async def leave(self, conn: Connection, room: str) -> None
    async def broadcast(self, room: str, event: str, payload: dict) -> None
    async def broadcast_all(self, event: str, payload: dict) -> None
    async def broadcast_except(self, exclude_id: str, event: str, payload: dict) -> None
    async def members(self, room: str) -> list[Connection]
    async def rooms_of(self, conn: Connection) -> list[str]
```

Large broadcasts are chunked internally:
```python
# Never asyncio.gather(50000 coroutines) — chunked automatically
async def _broadcast_chunked(connections, event, payload, chunk_size=500):
    for chunk in chunks(connections, chunk_size):
        await asyncio.gather(*[c.send(event, payload) for c in chunk])
```

One slow client never delays others. Individual send failures are caught per-connection and logged without breaking the broadcast.

### Layer 7 — Middleware Chain

```python
@socket.middleware
async def logging_middleware(conn: Connection, event: str, payload: dict, call_next: Callable):
    logger.info(f"{conn.id} → {event}")
    await call_next()
```

The middleware chain is compiled once at startup into a call chain. Zero overhead per event beyond the actual function calls. Order is deterministic and documented.

### Layer 8 — Lifecycle Hooks

```python
@socket.on_connect
async def on_connect(conn: Connection): ...

@socket.on_disconnect
async def on_disconnect(conn: Connection, reason: str): ...

@socket.on_error
async def on_error(conn: Connection, error: Exception): ...

@socket.on_room_join
async def on_room_join(conn: Connection, room: str): ...

@socket.on_room_leave
async def on_room_leave(conn: Connection, room: str): ...
```

### Layer 9 — Framework Adapters

Each adapter has exactly one job: accept the raw WebSocket from the framework, wrap it in a `Connection` object, hand it to `ConnectionManager`. That is all.

```python
# FastAPI
from socketspec.adapters.fastapi import mount
mount(socket, app)

# Starlette
from socketspec.adapters.starlette import mount
mount(socket, app)

# Django
# routing.py
from socketspec.adapters.django import as_asgi
urlpatterns = [path("ws/", as_asgi(socket))]

# Quart
from socketspec.adapters.quart import mount
mount(socket, app)
```

---

## 8. Event System — Directions & Contracts

### The Core Design Rule

Emitting, broadcasting, and room joining are **conditional outcomes of one logic flow.** They are not separate concerns. The handler body is always the single source of truth for behavior. `emits` and `broadcasts` inside `@socket.on()` are metadata for the docs registry only — they never control what actually happens.

### The Single Decorator Pattern

```python
@socket.on(
    "update_order",
    description="Update an order's status",
    tags=["orders"],
    emits=[
        Emits("order_ack", model=OrderAckPayload, description="Confirms the update result"),
    ],
    broadcasts=[
        Broadcasts("order_changed", room="order:{order_id}", model=OrderChangedPayload),
    ]
)
async def update_order(conn: Connection, payload: OrderPayload):
    # Logic is entirely yours — emit, broadcast, room join wherever the flow demands
    result = await db.update_order(payload.order_id, payload.status)

    if result.success:
        await socket.rooms.join(conn, f"order:{payload.order_id}")
        await conn.emit("order_ack", OrderAckPayload(success=True))
        await socket.rooms.broadcast(
            f"order:{payload.order_id}",
            "order_changed",
            OrderChangedPayload(**result.data)
        )
    else:
        await conn.emit("order_ack", OrderAckPayload(success=False, error=result.error))
        # No broadcast on failure — conditional, fully owned by handler
```

### With Dependency Injection

```python
@socket.on(
    "admin_broadcast",
    tags=["admin"],
    emits=[Emits("broadcast_ack", model=BroadcastAckPayload)],
    broadcasts=[Broadcasts("global_alert", room="notifications", model=AlertPayload)]
)
async def admin_broadcast(
    conn: Connection,
    payload: AlertPayload,
    user: User = Depends(require_admin),       # validated before handler runs
    db: AsyncSession = Depends(get_db)         # injected, same session reused
):
    await db.log_alert(user.id, payload.message)
    await socket.rooms.broadcast("notifications", "global_alert", payload.model_dump())
    await conn.emit("broadcast_ack", BroadcastAckPayload(success=True))
```

### What the Docs Engine Does With emits and broadcasts

The docs engine reads the `emits` and `broadcasts` metadata lists from the registry and renders the full frontend contract. It shows what this handler *can* emit and *can* broadcast. The conditional nature of when they fire is the developer's concern, not the docs'.

Frontend developers see: *"this handler may emit these events and may broadcast to these rooms"* — accurate, honest, and everything they need for integration.

### Error Envelope — System Standard

WebSockets have no status codes. The framework defines a standard error envelope. All errors, from all sources, always use this shape.

```python
{
    "event": "__error__",
    "payload": {
        "code": "VALIDATION_ERROR",
        "event": "send_message",
        "message": "Field 'text' is required",
        "request_id": "uuid-v4",
        "details": {
            "field": "text",
            "error": "field required"
        }
    }
}
```

**System error codes:**

| Code | Trigger |
|---|---|
| `VALIDATION_ERROR` | Pydantic fails on incoming payload |
| `AUTH_ERROR` | Auth check failed on connect |
| `AUTH_EXPIRED` | Token expired during live connection |
| `RATE_LIMIT_ERROR` | Token bucket exceeded |
| `PAYLOAD_TOO_LARGE` | Exceeds max_payload_size before Pydantic runs |
| `UNKNOWN_EVENT` | Event name not in registry |
| `ROOM_NOT_FOUND` | Broadcast to non-existent room |
| `PERMISSION_ERROR` | Room guard returned False |
| `HANDLER_ERROR` | Unhandled exception in user handler code |
| `SESSION_EXPIRED` | max_duration exceeded |
| `IDLE_TIMEOUT` | idle_timeout exceeded |

User handler errors are caught by the framework, formatted into this envelope, and emitted to the client. The connection stays alive. Handler errors never kill the connection.

### Connection Object — Available in Every Handler

```python
conn.id                        # UUID4, unique per connection
conn.identity                  # from auth — user_id, scopes, custom claims
conn.connected_at              # datetime
conn.last_active               # updated on every event
conn.rooms                     # set[str] — rooms this connection is in
conn.metadata                  # dict — user-settable, persists per connection
conn.session.expires_at        # when max_duration kicks in
conn.session.token_expires_at  # when JWT expires
conn.headers                   # HTTP upgrade request headers
conn.query_params              # HTTP upgrade request query params
```

---

## 9. Room Management

### Three Ways Rooms Come Into Existence

**Implicit rooms** — created on first join, destroyed on last leave.

```python
@socket.on("join_order_tracking")
async def join_order(conn: Connection, payload: JoinOrderPayload):
    await socket.rooms.join(conn, f"order:{payload.order_id}")
    await conn.emit("joined", {"room": f"order:{payload.order_id}"})
```

**Static rooms** — declared at startup, always exist regardless of membership.

```python
socket = SocketApp(
    rooms=[
        Room("notifications"),
        Room("admins", private=True)
    ]
)
```

**Protected rooms** — require a guard function before join is allowed.

```python
@socket.room_guard("order:{order_id}")
async def guard_order_room(conn: Connection, order_id: str) -> bool:
    return await db.user_owns_order(conn.identity.user_id, order_id)
```

Guard returns `False` → join rejected with `PERMISSION_ERROR`. Room is not created.

### Room Data Model

```python
@dataclass
class Room:
    name: str                    # "order:998" (live) or "order:{id}" (pattern)
    is_pattern: bool             # True when name contains {variables}
    private: bool = False        # requires guard function
    max_members: int | None = None
    ttl: int | None = None       # None = lives until empty
    metadata: dict = field(default_factory=dict)
```

### Auto-Join on Connect (optional)

```python
socket = SocketApp(
    auto_join_rooms=["notifications"]  # every client joins on connect
)
```

---

## 10. Docs UI

### Design Principle

Swagger is the reference. People already have muscle memory for it. We adapt the exact mental model and three-panel layout for WebSockets. The learning curve for anyone who has used Swagger is close to zero.

### Swagger → SocketSpec Mapping

| Swagger | SocketSpec |
|---|---|
| HTTP method badge (GET/POST) | Direction badge (📤 EMIT / 📥 LISTEN / 📡 BROADCAST) |
| Route path `/api/orders` | Event name `order_update` |
| Server URL dropdown | WS URL + 🟢/🔴 Connect toggle |
| Authorize button 🔒 | Auth token input (JWT / API key) |
| Tag groups | Namespace + tag groups |
| Request body schema | Payload In schema |
| Response schema | Payload Out schema |
| Try it out → Execute | Try it out → Send Event |
| Response section | Live response + broadcast log |

### What Each Event Card Shows

Every event renders as a collapsible card. Expanded view shows:

1. **Frontend Emits** — exact `socket.emit("event_name", {...})` with field names, types, required flags, descriptions
2. **Frontend Listens (direct response)** — exact `socket.on("response_event", ...)` with response schema
3. **Room Receives (broadcast)** — room pattern, which clients see it, exact `socket.on(...)` with schema
4. **On Error** — all error codes this event can produce, in the standard envelope shape

The frontend developer reads one card and knows exactly what to write. No backend context needed. A **Copy SDK** button generates ready-to-paste JavaScript/TypeScript/Python client code.

### Live Test Panel (Try it out)

Click "Try it out" on any event:
- JSON editor pre-populated with example payload from schema
- **Send Event** button fires the event over a real WebSocket to your server
- Goes through the **exact same middleware stack** as a real client — no bypass, no backdoor
- Response renders below (direct response + any broadcasts triggered)

### Rooms Panel

Separate section in the sidebar:

- Static rooms listed with current member count (dev mode only)
- Dynamic room patterns (e.g. `order:{order_id}`) listed with live instances below
- Click a room → shows which events broadcast to it, which events cause a join

### Live Socket Logs

Bottom drawer, always visible, real-time:

```
14:32:01  🟢 CONNECT    conn_a3f9   user_id: 42
14:32:04  📤 EMIT       conn_a3f9   send_message → {room: "lobby", text: "hi"}
14:32:04  📥 RESPONSE   conn_a3f9   message_sent ← {id: "msg_001", ts: "..."}
14:32:04  📡 BROADCAST  chat:lobby  new_message → 3 clients
14:32:08  ⚠️  ERROR     conn_b2e1   VALIDATION_ERROR: send_message / text required
14:32:15  🔴 DISCONNECT conn_a3f9   reason: client_close
```

Click any row → expands to full payload. Filter by type (connects / emits / broadcasts / errors). Search by connection ID or event name. Export to JSON. Clear button.

Logs are dev mode only. In production they go to your configured Python logger, never the UI.

### Enabling the Docs

```python
# Development — docs on by default
socket = SocketApp(docs=True, docs_url="/socket-docs")

# Deployed / staging — docs protected by access token
socket = SocketApp(
    docs=True,
    docs_url="/socket-docs",
    docs_access_token="staging-secret-token",
)

# Production — docs off by default, must explicitly enable
socket = SocketApp(docs=False)
```

---

## 11. Security Model

### Key Fact: WebSockets and CORS

WebSocket connections are NOT subject to browser CORS enforcement. Browsers don't send preflight requests for WebSocket connections. Any website can open a WebSocket to your server. The security mechanism is **Origin header validation during the HTTP upgrade handshake** — not CORS headers.

The attack this prevents is **Cross-Site WebSocket Hijacking (CSWSH)**: a malicious website opens a WebSocket using the victim's browser cookies to authenticate.

### Security Layers — In Order

```
1. TLS enforcement         ← wss:// only in production, ws:// blocked
2. Origin validation       ← at HTTP upgrade, before WS is open
3. Authentication          ← on connect, pluggable strategy
4. Payload size check      ← raw bytes, before deserialization
5. Pydantic validation     ← type safety, before handler
6. Rate limiting           ← token bucket, per connection
7. Room guards             ← per-room permission check
```

Each layer runs before the next. A failure at any layer stops processing and closes/rejects the connection at the appropriate stage.

### Configuration

```python
socket = SocketApp(
    # Origins
    allowed_origins=["https://myapp.com", "https://app.myapp.com"],

    # Auth
    auth=JWTAuth(secret="...", algorithm="HS256"),

    # Payload limits
    max_payload_size=65_536,     # 64KB in bytes

    # Rate limiting
    rate_limit=RateLimit(
        events=100,              # max events
        per_seconds=60,          # per time window
        strategy="token_bucket"
    ),
)
```

### Auth is a Protocol — Fully Pluggable

```python
class AuthBackend(Protocol):
    async def authenticate(
        self, headers: dict, query_params: dict
    ) -> Identity | None: ...
```

Ships with `JWTAuth` and `APIKeyAuth`. Contributors add OAuth, Session, custom — as separate adapter packages.

### Auth Token Expiry During Live Connection

JWT valid at connect. Connection lives 4 hours. JWT expires at hour 1.

Framework handles this automatically:
- At `token_refresh_window` seconds before expiry → emits `__auth_expiring__` to client
- Client responds with `__refresh_auth__` carrying new token
- If no refresh arrives within timeout → connection closed with `AUTH_EXPIRED`
- Frontend writes this handler once, globally, and it works for all connections

### Docs UI Security in Deployed Environments

The docs test UI connects from the same origin as the server. Same-origin WebSocket connections pass origin validation automatically. The test connection goes through the full auth middleware — no bypass. The docs page itself is protected by `docs_access_token` so only authorized developers can access it.

---

## 12. Session Management & TTL

### Session Config

```python
socket = SocketApp(
    session=SessionConfig(
        # Connection lifetime
        max_duration=7200,          # 2 hours hard cap
        idle_timeout=300,           # 5 min with no events

        # Heartbeat (system-managed ping/pong)
        heartbeat_interval=25,      # server pings every 25s
        heartbeat_timeout=10,       # no pong in 10s = dead connection

        # Auth token lifecycle
        token_refresh_window=60,    # warn client 60s before token expires

        # Redis TTL (connection state keys)
        redis_key_ttl=7800,         # max_duration + 10min buffer
    )
)
```

### What Each Config Does

**`max_duration`** — Hard cap on connection lifetime. At `max_duration - 60s`, server emits `__session_expiring__` as warning. At `max_duration`, server cleanly closes. Prevents ghost connections and memory leaks from clients that never properly disconnect.

**`idle_timeout`** — Connection with no incoming events for N seconds. Server emits `__idle_warning__` at `idle_timeout - 60s`. Closes at `idle_timeout`. Delivery systems want this low (60-120s). Chat platforms can be higher (600s+).

**`heartbeat_interval` + `heartbeat_timeout`** — Server sends a WebSocket ping frame every N seconds. The client's WebSocket library responds with pong automatically — no user code needed. If no pong arrives within `heartbeat_timeout`, the connection is dead. Removed from all rooms, state cleaned up, logs the disconnect. This catches half-open TCP connections that are invisible to application code.

**`redis_key_ttl`** — Every Redis key (connection state, room membership) gets this TTL. If a server crashes without graceful shutdown, Redis keys expire on their own. No stale state accumulates. No manual cleanup scripts needed.

---

## 13. Customization — What System Handles vs User

| Responsibility | Owner | Reason |
|---|---|---|
| Connection lifecycle (accept/close) | System | Infrastructure, easy to get wrong |
| Heartbeat / ping-pong | System | Infrastructure concern |
| Payload size enforcement | System | Security baseline, non-negotiable |
| Pydantic validation | System | Non-negotiable for reliability |
| asyncio.Lock on all state mutations | System | Race conditions must not be user's problem |
| Reconnection handling | System | Complex, error-prone |
| Docs generation | System | Automatic from registry |
| Error envelope formatting | System | Standard must be consistent |
| Graceful shutdown sequencing | System | Infrastructure |
| Heartbeat / ghost connection cleanup | System | Infrastructure |
| Redis key TTL management | System | Infrastructure |
| Broadcast chunking | System | Performance concern, invisible |
| Event handlers | User | Their business logic |
| Auth strategy | User (pluggable) | App-specific |
| Rate limit values | User (configurable) | Context-dependent |
| Middleware order | User | App-specific |
| Backend (memory/Redis) | User (one line) | Deployment decision |
| Namespace structure | User | App architecture |
| Room join/leave logic | User (with system APIs) | App-specific |
| Session TTL values | User (configurable) | App-specific |
| Connection metadata | User | App-specific |
| Room guard functions | User | Permission logic is always app-specific |

**The rule:** system handles anything that, if done wrong, causes security issues, race conditions, data loss, or crashes. User controls anything that varies per application.

---

## 14. Edge Cases & Critical Scenarios

These are the scenarios that only surface during real implementation and testing. All of them require explicit design decisions — not afterthoughts.

### Handler throws unhandled exception
**Decision:** Framework catches it, formats into `__error__` envelope, emits to client, connection stays alive. Handler errors never kill the connection. Logged at ERROR level.

### Client disconnects mid-broadcast
**Decision:** Per-connection `try/except` inside the broadcast gather, not around the whole gather. One failed send does not stop delivery to the remaining 499 connections.

### Event ordering (sequence-sensitive systems)
`asyncio.create_task` does not guarantee order. For delivery systems, `order_picked` arriving before `order_confirmed` is a bug.

**Decision:** Per-connection serialized queue, opt-in per event.

```python
@socket.on("order_update", ordered=True)
async def handle_order(conn, payload): ...
```

When `ordered=True`, events from that connection are queued and processed sequentially. Other connections unaffected.

### Memory leak — ghost connections
Client connects, never sends anything, never disconnects cleanly. TCP connection stays half-open.

**Decision:** Server-side heartbeat (ping/pong). If no pong within `heartbeat_timeout`, connection is forcibly closed and all state cleaned up. System-managed entirely.

### Late join problem
Client joins a room after a broadcast was sent. Has no idea what state the room is in (chat history, order status, etc.).

**Decision:** Framework does not solve this (it's application logic), but makes the pattern easy via `on_room_join` hook.

```python
@socket.on_room_join
async def send_history(conn: Connection, room: str):
    history = await db.get_last_messages(room)
    await conn.emit("room_history", history)
```

### Duplicate connection (same user, multiple tabs/devices)
Same `user_id`, different `connection_id`.

**Decision:** Framework does not block this. Exposes `conn.identity.user_id` so the application handles it — reject second connections, or track all connections per user in their own logic.

### Startup validation — duplicate event names
Two handlers registered for the same event name.

**Decision:** `DuplicateEventError` raised at import/startup time. Never at runtime.

### Startup validation — reserved event names
User tries to register `@socket.on("__error__")`.

**Decision:** `ReservedEventNameError` raised at startup.

### CPU-bound handlers blocking the event loop
A handler does heavy computation — PDF generation, ML inference, image processing. Blocks the event loop for all connections.

**Decision:** `executor=True` flag runs the handler in a threadpool automatically.

```python
@socket.on("generate_report", executor=True)
async def handle_report(conn, payload): ...
```

### Redis connection loss during operation
Redis goes down while connections are active.

**Decision:** Auto circuit-breaker. Falls back to memory-only mode during outage. System logs a WARNING. When Redis reconnects (exponential backoff), resumes normal operation. Fully automatic — no user configuration or handling required.

### Backpressure — broadcasting to large rooms
`asyncio.gather(50000 coroutines)` is not free and can spike memory.

**Decision:** Broadcast chunking at configurable `chunk_size=500` internally. User never sees this.

### Binary payloads
Some systems send binary data over WebSocket frames — audio chunks, file parts, image data.

**Decision:** Framework handles both JSON and binary frame types. Binary frames bypass Pydantic and go to a separate binary handler path.

```python
@socket.on_binary("audio_chunk")
async def handle_audio(conn: Connection, data: bytes): ...
```

### Graceful shutdown on SIGTERM
Server receives SIGTERM (deploy, restart, scale-down).

**Decision:** System-managed shutdown sequence:
1. Stop accepting new connections
2. Emit `__server_shutdown__` to all connected clients with a countdown
3. Wait for in-flight handlers to complete (with a configurable timeout)
4. Forcibly close any remaining connections
5. Clean up all Redis state

### Automated testing without a running server
The docs UI solves manual testing. CI/CD needs programmatic testing.

**Decision:** First-class `TestClient` as part of the package.

```python
from socketspec.testing import TestClient

async def test_send_message():
    client = TestClient(socket_app)
    async with client.connect() as conn:
        await conn.emit("send_message", {"room": "lobby", "text": "hi"})
        response = await conn.receive("message_sent")
        assert response["timestamp"] is not None
        broadcast = await conn.receive_broadcast("new_message", room="lobby")
        assert broadcast["text"] == "hi"
```

### Mixed content — ws:// from https:// page
**Decision:** Framework auto-detects and shows a visible warning in the docs UI. Documented prominently in deployment guide.

---

## 15. Python Module Standards

### Package Structure

```
socketspec/                         ← repo root
├── src/
│   └── socketspec/
│       ├── __init__.py             ← public API surface (what users import)
│       ├── app.py                  ← SocketApp class
│       ├── connection.py           ← Connection + Identity models
│       ├── registry.py             ← EventRegistry
│       ├── router.py               ← EventRouter
│       ├── manager.py              ← ConnectionManager
│       ├── rooms.py                ← RoomManager
│       ├── session.py              ← SessionConfig + TTL management
│       ├── backends/
│       │   ├── base.py             ← BackendAdapter Protocol
│       │   ├── memory.py           ← MemoryBackend
│       │   └── redis.py            ← RedisBackend
│       ├── adapters/
│       │   ├── fastapi.py
│       │   ├── starlette.py
│       │   ├── django.py
│       │   └── quart.py
│       ├── security/
│       │   ├── auth.py             ← AuthBackend Protocol + JWTAuth + APIKeyAuth
│       │   ├── ratelimit.py        ← TokenBucket implementation
│       │   └── origins.py          ← Origin validation
│       ├── docs/
│       │   ├── engine.py           ← reads EventRegistry, serves schema
│       │   └── ui/                 ← static HTML/JS/CSS for Swagger-style UI
│       ├── testing.py              ← TestClient
│       └── middleware.py           ← Middleware chain compilation
├── tests/
│   ├── unit/                       ← unit tests per module
│   ├── integration/                ← full stack tests
│   └── adapters/                   ← per-framework adapter tests
├── docs/                           ← MkDocs documentation site
│   ├── index.md
│   ├── quickstart.md
│   ├── adapters/
│   └── contributing/
├── examples/
│   ├── fastapi_example/
│   ├── django_example/
│   └── ai_streaming_example/
├── signatures/                     ← CLA signatures (auto-managed by CLA Assistant)
│   └── cla.json
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  ← tests + CLA check on every PR
│   │   └── publish.yml             ← publish to PyPI on version tag
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── adapter_request.md
│   └── PULL_REQUEST_TEMPLATE.md
├── pyproject.toml                  ← PEP 621, single source of truth
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── SECURITY.md
├── ROADMAP.md
├── AUTHORS                         ← Laiba Shahab as original author
├── NOTICE                          ← Required by Apache 2.0
├── CLA.md                          ← Contributor License Agreement
└── LICENSE                         ← Apache 2.0 full text
```

### Configuration Standard — pyproject.toml (PEP 621)

```toml
[build-system]
requires = ["hatchling >= 1.26"]
build-backend = "hatchling.build"

[project]
name = "socketspec"
version = "0.1.0"
description = "FastAPI-style WebSocket framework with built-in docs and testing"
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
authors = [{ name = "Laiba Shahab", email = "its.laiba.shahab@email.com" }]
dependencies = [
    "websockets>=12.0",
    "pydantic>=2.0",
    "anyio>=4.0",
]

[project.optional-dependencies]
redis  = ["redis>=5.0"]
fastapi = ["fastapi>=0.100"]
django  = ["django>=4.2"]
dev    = ["pytest", "pytest-asyncio", "ruff", "mypy", "pre-commit"]
```

### Required Toolchain

- **ruff** — linting + formatting (replaces black + flake8 + isort)
- **mypy (strict)** — static type checking, no `Any` in public API
- **pytest + pytest-asyncio** — async test support
- **pytest-cov** — coverage reporting, minimum 90% enforced in CI
- **towncrier** — automated CHANGELOG from PR fragments
- **pre-commit** — enforce standards before every commit

### Python Version Support

Minimum Python 3.10. Reason: structural pattern matching and better type union syntax. Tested in CI against 3.10, 3.11, 3.12, 3.13.

### Versioning

Semantic versioning (SemVer). `MAJOR.MINOR.PATCH`.

- PATCH: bug fixes, no API changes
- MINOR: new features, backward compatible
- MAJOR: breaking changes (rare, communicated well in advance)

---

## 16. GitHub & Community Setup

### Project Ownership

**Author and IP owner:** Laiba Shahab
**Copyright notice (appears in every source file):**
```python
# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0
# See LICENSE file in the project root for full license information.
```

This notice goes at the top of every `.py` file in `src/socketspec/`. No exceptions.

**`AUTHORS` file (repo root):**
```
SocketSpec was created and is maintained by Laiba Shahab.

Original Author:
  Laiba Shahab <its.laiba.shahab@email.com> — https://github.com/ByteCraftByLaiba
```

**`NOTICE` file (required by Apache 2.0, repo root):**
```
SocketSpec
Copyright 2025 Laiba Shahab

This product includes software developed by Laiba Shahab.
```

### License: Apache 2.0

Apache 2.0 over MIT for three reasons specific to Laiba's situation:

**Patent protection** — Apache 2.0 includes an explicit patent grant. Anyone who contributes code grants Laiba (and all users) a perpetual, royalty-free patent license for their contribution. Contributors cannot contribute code and later sue for patent infringement on that same code.

**Attribution enforced** — Anyone redistributing SocketSpec — including companies using it in commercial products — must reproduce the copyright notice and include the NOTICE file. Laiba's name stays attached to the work.

**License compatibility** — Apache 2.0 is compatible with GPL v3, allowing the community maximum flexibility, while still protecting Laiba's IP more robustly than MIT.

### Contributor License Agreement (CLA) — Mandatory

This is the most critical IP protection mechanism for any open source project.

**Without a CLA:** Every contributor retains copyright on their contribution. Laiba cannot relicense the project, pursue infringers, or use contributions commercially without tracking down every contributor individually.

**With a CLA:** Contributors grant Laiba a perpetual, worldwide, irrevocable license to their contributions. Laiba remains the sole IP owner of the complete project regardless of how many contributors join.

**Implementation:** Use [CLA Assistant](https://cla-assistant.io) — free, integrates directly with GitHub. When a contributor opens a PR:
1. CLA Assistant bot comments on the PR
2. Contributor clicks the link and signs electronically
3. PR cannot be merged until CLA is signed
4. Signature is recorded permanently

**Add to `CONTRIBUTING.md`:**
```markdown
## Contributor License Agreement

Before your first PR is merged, you will be asked to sign the SocketSpec CLA.
This assigns Laiba Shahab a license to your contribution while you retain
your own copyright. This is standard practice for open source projects and
protects everyone involved. The CLA bot will guide you through this automatically.
```

**Add to `.github/workflows/ci.yml`:**
```yaml
- name: CLA Check
  uses: contributor-assistant/github-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    PERSONAL_ACCESS_TOKEN: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
  with:
    path-to-signatures: 'signatures/cla.json'
    path-to-document: 'https://github.com/ByteCraftByLaiba/socketspec/blob/main/CLA.md'
```

**`CLA.md` (repo root)** — A simple CLA document stating:
- Contributor retains their copyright
- Contributor grants Laiba Shahab a perpetual, irrevocable, worldwide license to use, modify, sublicense, and distribute their contributions
- Contributor confirms they have the right to grant this license
- Signed electronically via CLA Assistant

### Required Files

**README.md** — first screen must contain:
- One sentence: what it solves
- Install command: `pip install socketspec`
- Minimal working example (under 25 lines)
- Badges: CI status, PyPI version, coverage, Python versions, license
- Link to full documentation

**CONTRIBUTING.md** — must answer:
- How to set up the dev environment (one command)
- How to run the tests
- How to write a new framework adapter (the most common contribution)
- How to write a new auth backend
- How to write a new storage backend
- PR checklist (tests written, types annotated, docs updated, CHANGELOG fragment added)
- Where `good first issue` labels are

**CODE_OF_CONDUCT.md** — Contributor Covenant v2.1. Standard, widely recognized.

**SECURITY.md** — how to report security vulnerabilities privately. Do not open a public issue for security bugs. Dedicated email.

**CHANGELOG.md** — auto-generated by towncrier from PR fragments. Human-readable, per-version.

**ROADMAP.md** — public, versioned milestones. This is the primary contributor funnel. People look at the roadmap, see something they need, and contribute.

### Issue Templates — Three Types

1. **Bug report** — reproduction steps, expected vs actual, Python version, framework, OS
2. **Feature request** — use case description, proposed API
3. **Adapter request** — "I want support for X framework" — structured form, links contributor directly to CONTRIBUTING.md adapter guide

### Labels That Build Community

```
good first issue      ← entry point for new contributors
help wanted           ← maintainer requests community help
adapter: django       ← framework-specific work
adapter: flask
backend: redis
backend: memcached
docs                  ← documentation improvements
security              ← gets priority treatment
breaking change       ← signals MAJOR version bump
```

### GitHub Actions

**ci.yml** — runs on every PR:
- Test matrix: Python 3.10, 3.11, 3.12, 3.13
- Frameworks: FastAPI, Django, Starlette
- Coverage check (fail below 90%)
- ruff lint check
- mypy type check

**publish.yml** — runs on version tag push:
- Runs full CI first
- Builds package
- Publishes to PyPI using scoped token

### Governance

Simple at first. Documented in GOVERNANCE.md:
- Maintainer (you): merge rights, release authority
- Trusted contributors: triage rights after 3+ merged PRs
- All breaking changes require maintainer approval
- Decisions made in GitHub Discussions, not in DMs

---

## 17. Open Source Strategy

### The Positioning

> *"OpenAPI gave HTTP a spec. SocketSpec does the same for WebSockets."*

This is a compelling story because it is true and because every FastAPI developer immediately understands the value. The name carries the pitch.

### Laiba Shahab as the Author

The project is publicly attributed to Laiba Shahab as creator and maintainer. This matters for:
- **Trust** — a named human behind the project signals accountability
- **IP** — copyright notices, CLA, and Apache 2.0 attribution all tie back to Laiba by name
- **Community** — contributors know exactly who maintains the project and who to reach

### The Trust Chain

```
Clean codebase → Contributors can read and understand it
      ↓
Easy contribution process → More contributors
      ↓
More contributors → More adapters, backends, and features
      ↓
More features + more users → Issues found and fixed faster
      ↓
Faster fixes + broader compatibility → Developer trust
      ↓
Developer trust → Production adoption
```

### Contribution Funnel (ordered by difficulty)

1. **Documentation fixes** — lowest barrier, first PR for many developers
2. **Example applications** — add examples for different domains (chat, IoT, streaming, AI, etc.)
3. **Auth adapters** — OAuth, Session, custom strategies
4. **Framework adapters** — Litestar, Sanic, Quart, Flask
5. **Backend adapters** — Redis (early milestone), Memcached, DynamoDB
6. **Sync support** — SyncSocketApp on top of the async core
7. **Core features** — binary payloads, ordered events, metrics integration

Each level in this funnel is a labeled category in GitHub Issues with a corresponding CONTRIBUTING.md section explaining exactly how to do it.

### What Makes Contributors Come Back

- PR reviewed within 48 hours (not left open for months)
- Clear feedback, not vague requests
- Credit in CHANGELOG and README contributors section
- Assigned as adapter maintainer for frameworks they contributed
- Roadmap updated publicly when their contribution closes a milestone

---

## 18. Build Roadmap

### Phase 1 — Core (Maintainer builds this)

The foundation everything else depends on.

- `Connection` + `ConnectionManager` (memory backend only)
- `EventRegistry` + `EventRouter`
- `@socket.on()` with `emits` and `broadcasts` as metadata params
- `Emits` and `Broadcasts` dataclasses for registry metadata
- Pydantic payload validation
- Error envelope system
- FastAPI adapter
- Docs UI — single client, Swagger-style layout, live test panel
- Docs UI — one hint line on the connection bar: *"Open another tab to test as a different client"*
- Basic socket logs in docs UI
- `SessionConfig` with `heartbeat`, `idle_timeout`, `max_duration`
- `TestClient` for automated testing
- CI/CD pipeline + CLA Assistant
- README, CONTRIBUTING.md, full docs site
- `.context/SYSTEM_v0.1.0.md` written before code is committed

**Deliverable:** `v0.1.0` — working on FastAPI, full docs UI, testable in browser.

### Phase 2 — Expand Compatibility

- Django adapter
- Starlette adapter
- Quart adapter
- Origin validation + `allowed_origins` config
- `JWTAuth` + `APIKeyAuth`
- `RateLimit` with token bucket
- Room guards
- `ROADMAP.md` published, `adapter_request` issue template live
- `.context/SYSTEM_v0.2.0.md` updated from v0.1.0

**Deliverable:** `v0.2.0`

### Phase 3 — Production Readiness

- Redis backend
- Multi-server broadcast model
- `ordered=True` per-event queue
- Graceful shutdown on SIGTERM
- Redis circuit breaker with memory fallback
- Binary payload support
- `executor=True` threadpool handler flag
- Full OWASP WebSocket security checklist compliance
- `.context/SYSTEM_v0.3.0.md` updated

**Deliverable:** `v0.3.0`

### Phase 4 — Ecosystem + Docs v2

- Litestar adapter
- Sanic adapter
- Prometheus metrics integration
- OpenTelemetry tracing
- `docs_access_token` protection for deployed environments
- `Copy SDK` button in docs UI (JS, TS, Python client snippets)
- **Multi-client panel in docs UI** — spawn multiple virtual clients, persona system, unified log
- `.context/SYSTEM_v0.4.0.md` updated

**Deliverable:** `v0.4.0`

### Phase 5 — Stable + Community

- Sync support (`SyncSocketApp`) — community-led
- Memcached backend — community-led
- Django Channels compatibility layer — community-led
- Full async test coverage across all adapters
- Security audit
- `v1.0.0` stable API declaration
- `.context/SYSTEM_v1.0.0.md` final stable snapshot

**Deliverable:** `v1.0.0`

---

## End-to-End Example — What the Developer Writes

This is the final proof of the design. A developer building a real-time platform with tracking and chat:

```python
from socketspec import SocketApp, Connection, Room, Emits, Broadcasts
from socketspec.security import JWTAuth
from socketspec.session import SessionConfig
from pydantic import BaseModel

socket = SocketApp(
    docs=True,
    auth=JWTAuth(secret="my-secret"),
    backend="redis",
    allowed_origins=["https://myapp.com"],
    session=SessionConfig(max_duration=3600, idle_timeout=300),
    rooms=[Room("notifications")],
)

# ── Tracking ─────────────────────────────────────────────────

class JoinTrackingPayload(BaseModel):
    entity_id: str

class UpdatePayload(BaseModel):
    entity_id: str
    status: str

class UpdateAckPayload(BaseModel):
    success: bool
    timestamp: str

class UpdateChangedPayload(BaseModel):
    entity_id: str
    status: str
    updated_by: str

@socket.room_guard("tracking:{entity_id}")
async def guard_tracking_room(conn: Connection, entity_id: str) -> bool:
    return await db.user_can_access(conn.identity.user_id, entity_id)

@socket.on("join_tracking", description="Subscribe to entity updates", tags=["tracking"])
async def join_tracking(conn: Connection, payload: JoinTrackingPayload):
    await socket.rooms.join(conn, f"tracking:{payload.entity_id}")
    await conn.emit("joined", {"room": f"tracking:{payload.entity_id}"})

@socket.on(
    "update_status",
    description="Update entity status",
    tags=["tracking"],
    emits=[
        Emits("update_ack", model=UpdateAckPayload, description="Confirms update result")
    ],
    broadcasts=[
        Broadcasts("status_changed", room="tracking:{entity_id}", model=UpdateChangedPayload)
    ]
)
async def update_status(conn: Connection, payload: UpdatePayload):
    result = await db.update_status(payload.entity_id, payload.status)

    if result.success:
        await conn.emit("update_ack", UpdateAckPayload(success=True, timestamp=result.ts))
        await socket.rooms.broadcast(
            f"tracking:{payload.entity_id}",
            "status_changed",
            UpdateChangedPayload(
                entity_id=payload.entity_id,
                status=payload.status,
                updated_by=conn.identity.user_id
            )
        )
    else:
        await conn.emit("update_ack", UpdateAckPayload(success=False, timestamp=""))

# ── Chat ─────────────────────────────────────────────────────

class MessagePayload(BaseModel):
    room: str
    text: str

class MessageAckPayload(BaseModel):
    message_id: str
    timestamp: str

class NewMessagePayload(BaseModel):
    from_user: str
    text: str
    timestamp: str

@socket.on(
    "send_message",
    description="Send a message to a room",
    tags=["chat"],
    emits=[
        Emits("message_ack", model=MessageAckPayload, description="Delivery confirmation")
    ],
    broadcasts=[
        Broadcasts("new_message", room="chat:{room}", model=NewMessagePayload)
    ]
)
async def send_message(conn: Connection, payload: MessagePayload):
    msg = await db.save_message(conn.identity.user_id, payload.room, payload.text)
    await conn.emit("message_ack", MessageAckPayload(message_id=msg.id, timestamp=msg.ts))
    await socket.rooms.broadcast(
        f"chat:{payload.room}",
        "new_message",
        NewMessagePayload(from_user=conn.identity.user_id, text=payload.text, timestamp=msg.ts)
    )

# ── Mount ─────────────────────────────────────────────────────

from fastapi import FastAPI
from socketspec.adapters.fastapi import mount

app = FastAPI()
mount(socket, app)

# Docs live at http://localhost:8000/socket-docs
# Every event documented, testable, and readable by frontend
# No HTML file. No Postman workaround. No waiting for frontend.
```

---

*This document represents the complete shared understanding of the project — from the original pain, through every design decision, to the final implementation roadmap. It is the foundation on which the codebase is built.*
