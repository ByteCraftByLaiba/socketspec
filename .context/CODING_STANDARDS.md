# SocketSpec — Coding Standards
**Author:** Laiba Shahab
**Version:** v0.1.0
**Status:** Immutable — changes require maintainer approval and a new version entry

> These standards apply to every file in src/socketspec/ and tests/.
> No PRs are merged that violate these.
> AI tools read this file before writing any code.

---

## File Structure — Every Python File in This Order

```python
# 1. Copyright header
# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0
# See LICENSE file in the project root for full license information.

# 2. Module docstring
"""
One-line summary.

Extended explanation. What this module owns. What it does NOT own.
"""

# 3. __future__
from __future__ import annotations

# 4. Standard library imports (alphabetical)
import asyncio
import logging

# 5. Third-party imports (alphabetical)
from pydantic import BaseModel

# 6. Internal imports (absolute, alphabetical)
from socketspec.errors import SocketSpecError

# 7. Logger
logger = logging.getLogger(__name__)

# 8. Constants
MAX_SOMETHING = 500

# 9. Type aliases
HandlerFunc = Callable[..., Any]

# 10. Classes and functions
```

---

## Naming

| Thing | Convention | Example |
|---|---|---|
| Classes | PascalCase | `ConnectionManager` |
| Functions / methods | snake_case | `handle_connect` |
| Private methods | `_snake_case` | `_validate_payload` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_PAYLOAD_SIZE` |
| Type aliases | PascalCase | `ConnectionId` |
| Files | `snake_case.py` | `connection_manager.py` |
| Test files | `test_module_name.py` | `test_connection_manager.py` |
| Test functions | `test_what_when_condition` | `test_connect_rejects_invalid_origin` |

---

## Type Hints — Mandatory on Everything

```python
# CORRECT
async def handle_event(
    self,
    conn: Connection,
    raw_message: str | bytes,
) -> None: ...

# WRONG
async def handle_event(self, conn, raw_message): ...
```

- `mypy --strict` must pass with zero errors on every commit
- Never bare `Any` in public API (`__init__.py` exports)
- `Any` in internal code requires a `# type: ignore[misc]` comment
- Use `X | None` not `Optional[X]`
- Use `dict`, `list`, `tuple` not `Dict`, `List`, `Tuple`
- Use `type[X]` not `Type[X]`
- All `Protocol` classes must be `@runtime_checkable`

---

## Docstrings — Google Style, Mandatory on All Public Symbols

```python
class ConnectionManager:
    """Owns all live WebSocket connections.

    Single source of truth for connection state. No other module
    stores Connection objects directly.

    Note:
        Thread-safe via asyncio.Lock on all state mutations.
    """

    async def connect(self, conn: Connection) -> None:
        """Register a new connection and inject its capabilities.

        Args:
            conn: The Connection object built by the framework adapter.

        Raises:
            DuplicateConnectionError: If conn.id already exists.
        """
```

- Every public class: summary + extended description + Note if non-obvious
- Every public method: summary + Args + Returns (if non-None) + Raises
- Private methods: docstring only if logic is non-obvious
- No useless one-word docstrings (`"""Connect."""`)

---

## Async Patterns

```python
# CORRECT — create_task for fire-and-forget
asyncio.create_task(self._run_handler(conn, definition, payload))

# CORRECT — lock via async with
async with self._lock:
    self._connections[conn.id] = conn

# CORRECT — always re-raise CancelledError
try:
    await asyncio.sleep(interval)
except asyncio.CancelledError:
    raise  # never swallow

# WRONG — bare coroutine not awaited
self._run_handler(conn, definition, payload)  # does nothing

# WRONG — manual lock acquire/release
await self._lock.acquire()
...
self._lock.release()  # won't run on exception

# WRONG — swallowing CancelledError
except asyncio.CancelledError:
    pass  # task hangs, never cleans up
```

- Never `asyncio.run()` inside async context
- Never call a coroutine without `await` or `asyncio.create_task()`
- Always re-raise `asyncio.CancelledError`
- Always `async with` for locks
- Use `anyio` primitives where possible

---

## Error Handling

```python
# CORRECT
try:
    await conn.raw_socket.send_json(message)
except WebSocketDisconnect:
    logger.debug("Connection %s closed before send", conn.id)
except Exception:
    logger.error("Unexpected send failure for %s", conn.id, exc_info=True)

# WRONG — bare except
try:
    ...
except:
    pass

# WRONG — silent failure
except Exception:
    pass  # impossible to debug
```

- Never bare `except:`
- Never catch `BaseException`
- Never `pass` on exception without a log call
- Unexpected exceptions logged at `ERROR` with `exc_info=True`
- All custom exceptions inherit from `SocketSpecError`
- Exceptions in public API documented in `Raises:` docstring section

---

## Logging

```python
# Module logger — always this, never deviate
logger = logging.getLogger(__name__)

# Level usage
logger.debug("Connection %s received: %s", conn.id, event)  # trace
logger.info("Connection %s established", conn.id)            # lifecycle
logger.warning("Redis unavailable, falling back to memory")  # degraded
logger.error("Handler failed: %s", event, exc_info=True)     # failure

# WRONG
print(f"Connection {conn.id} connected")        # never print in library
logger.debug(f"Connection {conn.id} received")  # no f-strings in log calls
```

- `logging.getLogger(__name__)` in every module
- Never `print()` in library code
- Use `%` formatting in log calls, not f-strings
- Never log secrets, tokens, or full payloads at INFO or above

---

## Constants — Zero Magic Values

```python
# CORRECT
BROADCAST_CHUNK_SIZE = 500  # prevents asyncio.gather memory spikes on large rooms

RESERVED_EVENTS: frozenset[str] = frozenset({
    "__connect__",
    "__error__",
})

# WRONG
for chunk in self._chunks(members, 500):   # what is 500?
    ...

if event.startswith("__"):                 # fragile, inconsistent
    ...
```

- All numeric limits as module-level named constants with explanation comment
- All reserved event names in `RESERVED_EVENTS` frozenset in `errors.py`
- All error code strings in one place in `errors.py`
- No string literals repeated more than once

---

## Imports — Absolute Only

```python
# CORRECT
from socketspec.connection import Connection
from socketspec.errors import SocketSpecError

# WRONG
from .connection import Connection
from ..errors import SocketSpecError
```

- No relative imports anywhere in `src/socketspec/`
- No circular imports (follow build order in implementation plan)
- `__init__.py` is the only file that re-exports symbols

---

## Test Standards

```python
# CORRECT naming
async def test_connect_rejects_origin_not_in_allowed_list() -> None: ...
async def test_broadcast_skips_disconnected_member_silently() -> None: ...

# WRONG naming
async def test_connect() -> None: ...
async def test_broadcast() -> None: ...

# CORRECT — one behaviour per test
async def test_rate_limiter_blocks_after_limit_exceeded() -> None:
    limiter = TokenBucket(RateLimit(events=2, per_seconds=60))
    assert await limiter.consume("conn_1") is True
    assert await limiter.consume("conn_1") is True
    assert await limiter.consume("conn_1") is False
```

- Name format: `test_<what>_<condition>_<expected_outcome>`
- One primary assertion per test
- No shared mutable state between tests
- Fixtures in `conftest.py` only
- No `time.sleep()` — use `anyio.sleep()` or mock time
- `asyncio_mode = "auto"` set in pyproject.toml — no decorator needed
- Mock at the boundary (`BackendAdapter`), not internals

---

## Git Commits — Conventional Commits

```
feat(registry): add deprecated flag to EventDefinition
fix(manager): prevent duplicate connection on UUID collision
docs(readme): add Redis backend example
test(rooms): add broadcast to non-existent room coverage
refactor(router): extract payload size check to helper
chore(ci): add Python 3.13 to test matrix
security(auth): validate algorithm to prevent none attack
adapter(django): add Django ASGI adapter
```

Format: `type(scope): description`
Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `security`, `adapter`, `backend`

- Present tense, lowercase, no period
- Breaking change: `feat(app)!: rename serve() to mount()`
- Every commit must pass CI before merge to main
