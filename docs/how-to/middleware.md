# Middleware

Middleware wraps every event handler, allowing you to run logic before and after handler execution. SocketSpec middleware follows the same `next_handler` pattern used by ASGI middleware frameworks.

---

## Registering Middleware

Use the `@socket.middleware` decorator. Middleware functions receive the connection, event name, payload, and a `next_handler` callable:

```python
from socketspec import SocketApp, Connection

socket = SocketApp()

@socket.middleware
async def log_events(conn: Connection, event: str, payload: dict, next_handler):
    print(f"[{conn.id}] --> {event}")
    await next_handler(conn, event, payload)
    print(f"[{conn.id}] <-- {event} handled")
```

You must call `await next_handler(conn, event, payload)` to pass control to the next middleware or the final handler. If you do not call it, the handler is never executed.

---

## Execution Order

Middleware runs in FIFO (first-in, first-out) order. The first middleware registered is the outermost layer:

```python
@socket.middleware
async def middleware_a(conn, event, payload, next_handler):
    print("A: before")
    await next_handler(conn, event, payload)
    print("A: after")

@socket.middleware
async def middleware_b(conn, event, payload, next_handler):
    print("B: before")
    await next_handler(conn, event, payload)
    print("B: after")
```

Execution order for an inbound event:

```
A: before
  B: before
    handler executes
  B: after
A: after
```

---

## Common Patterns

### Timing

```python
import time

@socket.middleware
async def timing_middleware(conn, event, payload, next_handler):
    start = time.perf_counter()
    await next_handler(conn, event, payload)
    elapsed = time.perf_counter() - start
    logger.info("Event %s took %.3fs", event, elapsed)
```

### Error Enrichment

```python
@socket.middleware
async def error_context(conn, event, payload, next_handler):
    try:
        await next_handler(conn, event, payload)
    except Exception as exc:
        logger.error("Error in %s for conn %s: %s", event, conn.id, exc)
        raise  # re-raise so SocketSpec sends the HANDLER_ERROR envelope
```

### Conditional Blocking

```python
@socket.middleware
async def maintenance_mode(conn, event, payload, next_handler):
    if MAINTENANCE_MODE and event != "__pong__":
        await conn.emit("__error__", {
            "code": "MAINTENANCE",
            "message": "Server is under maintenance. Please try again later.",
        })
        return  # do not call next_handler
    await next_handler(conn, event, payload)
```

---

## Middleware and System Events

Middleware runs for all user events. System events (`__pong__`, `__refresh_auth__`) are handled before the middleware chain and are never passed through middleware.

---

## Testing Middleware

Middleware is fully active in `TestClient`. No special configuration is needed:

```python
from socketspec.testing import TestClient

async def test_middleware_runs():
    client = TestClient(socket)
    async with client.connect() as conn:
        await conn.emit("my_event", {"key": "value"})
        response = await conn.receive("my_response")
        # assertions here
```
