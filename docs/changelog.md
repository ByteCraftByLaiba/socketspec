# Changelog

All notable changes to SocketSpec are documented here. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## v0.1.3 — 2026-08-08

### Security

- `APIKeyAuth`: replaced `==` comparison with `hmac.compare_digest()` to prevent timing-attack-based key enumeration.
- Docs access token: replaced `==` comparisons with `hmac.compare_digest()` in `_check_docs_access` (bearer header and query-param paths).

### Fixed

- Heartbeat race condition: `pong_event.clear()` is now called *before* `conn.emit("__ping__")` so a fast pong arriving before the next line is never silently dropped, killing a healthy connection.
- FastAPI adapter: exceptions raised by `handle_event()` are now isolated inside the receive loop — a transient handler error no longer tears down the entire WebSocket connection.
- FastAPI adapter: `_graceful_shutdown()` is now guaranteed to run via `try/finally` around the lifespan `yield`, preventing resource leaks on crash.
- FastAPI adapter: auth rejection after `websocket.accept()` now sends explicit close code `1008 Policy Violation` instead of a silent `1000`.
- `TestConnection.receive()`: non-matching messages are now buffered and re-checked on subsequent calls instead of being silently discarded.
- Debug SSE: each connected client now receives its own queue (fan-out) via `_debug_subscribe` / `_debug_unsubscribe` so multiple open browser tabs each see every log entry.
- `MemoryBackend.publish()`: pub/sub callbacks are now dispatched concurrently with `asyncio.gather(return_exceptions=True)` to eliminate head-of-line blocking.
- `RoomManager.join()`: a rollback now removes the connection from the backend and `conn.rooms` if a join hook raises, keeping state consistent.
- `EventRegistry.validate()`: misleading docstring corrected to reflect actual behaviour.
- Removed unused `websockets>=12.0` core dependency.
- Test suite: improved assertion coverage in `test_coverage_gaps.py`; fixed misleading `test_same_depends_used_twice_called_once` test name and assertions.
- `OriginValidator`: documented exact-match limitation (port and trailing-slash edge cases) in the docstring.

---

## v0.1.2 — 2026-06-27

### Added

- Debug mode (`SocketApp(debug=True)`) with live event streaming at `/socket-debug`
- Swagger UI parity: exact match of OpenAPI-style schema layout in the docs UI
- Updated examples: `fastapi_chat`, `fastapi_notifications`, `ai_streaming`

---

## v0.1.1 — 2025-12-01

### Added

- First stable release with production-ready features
- Complete test coverage infrastructure (`pytest`, `anyio`, coverage reporting)

---

## v0.1.0 — 2025-10-01

Initial public release.

### Added

- `SocketApp` — FastAPI-style WebSocket application class with decorator-based event registration (`@socket.on`)
- `Connection` — per-connection object with `emit()`, `disconnect()`, `rooms`, `identity`, and `session` attributes
- `EventRegistry` — validates for duplicate events and reserved names at startup
- `EventRouter` — ordered and unordered dispatch queues with sentinel-based cleanup on disconnect
- `ConnectionManager` — lock-protected connection state
- `OriginValidator` — wildcard and exact-match origin checking
- `TokenBucket` — token-bucket rate limiter per connection
- `JWTAuth` — PyJWT-backed authentication backend
- `APIKeyAuth` — header or query-param API key authentication
- `RoomManager` — pattern-based room matching with `{variable}` expansion to named capture groups
- Room guards via `@socket.room_guard("pattern")` decorator
- `SessionManager` — per-connection heartbeat, idle timeout, max-duration enforcement, token expiry warning
- `Depends()` — FastAPI-compatible dependency injection with `AsyncExitStack` cleanup
- `MiddlewareChain` — FIFO middleware compiled once at startup
- FastAPI adapter with `mount()` helper
- `TestClient` and `TestConnection` for in-process testing without a server
- `SocketApp(docs=True)` — interactive documentation UI at `/socket-docs`
- Full `mypy --strict` compliance across the codebase
