# Roadmap

SocketSpec follows a phased delivery model. Each phase adds a layer without
breaking the public API established in the previous phase.

---

## ✅ v0.1.0 — Foundation (Current)

The core framework. Everything a FastAPI developer needs to build a
production WebSocket API.

- **Core engine** — `SocketApp`, `EventRegistry`, `EventRouter`, `ConnectionManager`
- **Security** — `OriginValidator`, `TokenBucket`, `JWTAuth`, `APIKeyAuth`
- **Rooms** — regex pattern matching, room guards, chunked broadcasts
- **Session** — heartbeat ping/pong, idle timeout, max-duration, token expiry warning
- **DI** — `Depends()` with yield-based cleanup via `AsyncExitStack`
- **Middleware** — FIFO chain compiled at startup
- **FastAPI adapter** — `mount()` helper
- **Memory backend** — in-process pub/sub and room storage
- **Docs UI** — Swagger-style interactive event browser at `/socket-docs`
- **TestClient** — in-process testing without a real server

---

## 🔜 v0.2.0 — Adapters

Bring SocketSpec to all major Python async frameworks.

- **Starlette adapter** — `socketspec.adapters.starlette`
- **Django Channels adapter** — `socketspec.adapters.django`
- **Quart adapter** — `socketspec.adapters.quart`
- **Sync adapter** (community milestone) — thin wrapper for sync Django views
- Cross-adapter integration test suite

---

## 🔜 v0.3.0 — Scale

Production-grade horizontal scaling.

- **Redis backend** — `socketspec.backends.redis`; pub/sub across multiple
  server instances using `redis>=5.0`
- **Binary WebSocket frames** — `bytes` payload support alongside JSON
- **Graceful shutdown** — drain in-flight events before process exit
- **Connection resumption** — reconnect with session token and replay missed
  events (best-effort, configurable window)

---

## 🔜 v0.4.0 — Observability

Production visibility without manual instrumentation.

- **Prometheus metrics** — connection count, event rate, error rate,
  queue depth, heartbeat latency
- **OpenTelemetry traces** — per-event spans with W3C trace context propagation
- **Structured logging** — JSON log output with correlation IDs
- **Health endpoint** — `/socket-health` returning backend status and
  active connection count

---

## 🔜 v0.5.0 — Developer Experience

- **Multi-client docs panel** — connect as multiple users simultaneously in
  the docs UI; see broadcasts delivered to all tabs in real time
- **Event replay** — replay any event from the log drawer
- **Schema export** — `socketspec export-schema` CLI command outputs
  the event schema as JSON or YAML
- **VS Code extension** — IntelliSense for `@socket.on()` event names and
  payload types

---

## Community Milestones

These are delivered by community contributors with maintainer review:

| Milestone | Description |
|---|---|
| Community sync adapter | Synchronous Django view support |
| AWS Lambda adapter | WebSocket API Gateway integration |
| Strawberry GraphQL subscriptions | Thin bridge over SocketSpec rooms |

---

*This roadmap reflects current intentions, not commitments.
Priorities may shift based on community feedback and usage patterns.*
