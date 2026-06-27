# Changelog

All notable changes to SocketSpec are documented here.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Changelog entries are generated from fragment files in `changes/` using
[Towncrier](https://towncrier.readthedocs.io/).

---

## v0.1.0 — 2025

Initial public release of SocketSpec.

### Added

**Core framework**
- `SocketApp` — FastAPI-style WebSocket application class with decorator-based
  event registration (`@socket.on`)
- `Connection` — per-connection object with `emit()`, `disconnect()`, `rooms`,
  `identity`, and `session` attributes
- `EventRegistry` — single source of truth for all registered events;
  validates for duplicates and reserved names at startup
- `EventRouter` — ordered and unordered dispatch queues with sentinel-based
  cleanup on disconnect
- `ConnectionManager` — `asyncio.Lock`-protected connection state;
  raises `DuplicateConnectionError` on duplicate registration

**Security**
- `OriginValidator` — wildcard and exact-match origin checking
- `TokenBucket` — continuous token-bucket rate limiter per connection
- `JWTAuth` — PyJWT-backed authentication backend
- `APIKeyAuth` — header or query-param API key authentication

**Rooms**
- `RoomManager` — regex-based room pattern matching; `{variable}` patterns
  expand to named capture groups passed to guard functions
- Room guards via `@socket.room_guard("pattern")` decorator
- Chunked broadcasts to avoid blocking the event loop on large rooms

**Session management**
- `SessionManager` — per-connection heartbeat (`__ping__` / `__pong__`),
  idle timeout, max-duration enforcement, token expiry warning
- Pong timeout detection — disconnects ghost connections on flaky networks
- `_auth_expiry_warned` guard — token expiry warning fires once per session,
  not on every heartbeat tick

**Dependency injection**
- `Depends()` — FastAPI-compatible dependency declaration
- `DependencyResolver` — yield-based cleanup via `AsyncExitStack`

**Middleware**
- `MiddlewareChain` — FIFO middleware compiled once at startup
- Middleware receives `(conn, event, payload, next_handler)` signature

**Adapters**
- `socketspec.adapters.fastapi` — `mount()` helper; `FastAPISocketWrapper`
  bridges FastAPI WebSocket to `RawSocket` protocol

**Built-in docs UI**
- Interactive Swagger-style event browser at `/socket-docs`
- Events grouped by tag with collapsible sections
- Direction badges: `📤 EMIT` (green), `📥 LISTEN` (blue), `📡 BROADCAST` (purple)
- Payload schema rendered as property table (Name / Type / Required / Description)
- Try-it-out flow: pre-filled JSON editor → Send → inline response
- Live log drawer with filter
- Connection status bar with multi-tab hint
- Dark mode support via `prefers-color-scheme`

**Testing**
- `TestClient` — in-process WebSocket test client; no server required
- `TestConnection` and `TestRawSocket` — in-memory queue simulation

**Backends**
- `MemoryBackend` — `asyncio.Lock`-protected in-memory pub/sub and room storage
  with automatic cleanup of empty rooms on disconnect

**Error system**
- `ERROR_CODES` frozenset with 11 system error codes
- `RESERVED_EVENTS` frozenset with 10 system event names
- Structured `__error__` envelope: `{code, event, message, request_id, details}`

### Security layer order (fixed, cannot be changed by middleware)

```
Origin → Auth → Payload Size → JSON Parse → Rate Limit → Middleware → DI → Handler
```

### Known limitations in v0.1.0

- Redis backend not yet implemented (Phase 3)
- Starlette, Django, and Quart adapters not yet implemented (Phase 2)
- Binary WebSocket frames not supported

---

*Unreleased changes are tracked as fragment files in `changes/`.*
