# SocketSpec — Complete Implementation Plan
> This document is the single instruction set for building SocketSpec from zero to open source.
> Every file, every module, every decision is specified here.
> Cursor implements this top to bottom. No ambiguity. No decisions left open.
>
> **Project owner and IP holder:** Laiba Shahab
> **License:** Apache 2.0
> **PyPI name:** socketspec

---

## Table of Contents

1. [Competitive Position](#1-competitive-position)
2. [Technology Stack](#2-technology-stack)
3. [Complete Project Structure](#3-complete-project-structure)
4. [Implementation Order](#4-implementation-order)
5. [Module Specifications](#5-module-specifications)
6. [Docs UI Specification](#6-docs-ui-specification)
7. [Test Plan](#7-test-plan)
8. [Documentation Site](#8-documentation-site)
9. [GitHub Configuration](#9-github-configuration)
10. [PyPI Publishing](#10-pypi-publishing)
11. [Launch Checklist](#11-launch-checklist)

---

## 1. Competitive Position

### What Exists vs What We Are

| Feature | FastWS | ChanX | pubsub | socketio | **SocketSpec** |
|---|---|---|---|---|---|
| FastAPI-style decorators | ✓ | partial | ✗ | ✗ | ✓ |
| Pydantic validation | ✓ | ✓ | ✓ | ✗ | ✓ |
| Live interactive test UI | ✗ | ✗ | ✗ | ✗ | **✓** |
| Multi-framework support | FastAPI only | Django-centric | FastAPI only | multi | ✓ |
| Rooms + broadcasting | ✗ | ✓ | topics only | ✓ | ✓ |
| Redis backend | ✗ | ✓ | ✓ | ✓ | ✓ |
| DI support | ✗ | ✗ | ✓ | ✗ | ✓ |
| Single-line mounting | ✗ | ✗ | ✗ | ✗ | **✓** |
| Zero external protocol | ✓ | ✓ | ✓ | ✗ | ✓ |

### The One-Line Pitch
> *"SocketSpec is what FastAPI is for HTTP — but for WebSockets. Define events with decorators, validate with Pydantic, and get an interactive docs UI out of the box."*

---

## 2. Technology Stack

### Runtime Dependencies (keep minimal)
```toml
python = ">=3.10"
websockets = ">=12.0"        # raw WS transport
pydantic = ">=2.0"           # validation + schema
anyio = ">=4.0"              # async primitives (asyncio + trio compat)
```

### Optional Dependencies
```toml
redis = { version = ">=5.0", optional = true }       # RedisBackend
fastapi = { version = ">=0.100", optional = true }   # FastAPI adapter
django = { version = ">=4.2", optional = true }      # Django adapter
```

### Dev Dependencies
```toml
pytest = ">=8.0"
pytest-asyncio = ">=0.23"
pytest-cov = ">=4.0"
httpx = ">=0.27"             # for TestClient HTTP side
ruff = ">=0.4"               # lint + format
mypy = ">=1.10"
pre-commit = ">=3.7"
mkdocs-material = ">=9.5"    # documentation site
towncrier = ">=23.0"         # changelog
```

### Build Backend
```toml
[build-system]
requires = ["hatchling>=1.26"]
build-backend = "hatchling.build"
```

### Python Version Strategy
- Minimum: 3.10 (structural pattern matching, `X | Y` union syntax)
- CI matrix: 3.10, 3.11, 3.12, 3.13

---

## 3. Complete Project Structure

```
socketspec/                              # repo root
│
├── src/
│   └── socketspec/
│       ├── __init__.py                  # public API — everything users import
│       ├── _version.py                  # single source of version
│       ├── types.py                     # shared type aliases
│       ├── errors.py                    # all exception classes
│       ├── connection.py                # Connection + Identity dataclasses
│       ├── registry.py                  # EventRegistry + EventDefinition
│       ├── router.py                    # EventRouter
│       ├── manager.py                   # ConnectionManager
│       ├── rooms.py                     # RoomManager
│       ├── session.py                   # SessionConfig + TTL logic
│       ├── middleware.py                # Middleware chain
│       ├── di.py                        # Depends() resolution
│       ├── app.py                       # SocketApp (main class)
│       │
│       ├── backends/
│       │   ├── __init__.py
│       │   ├── base.py                  # BackendAdapter Protocol
│       │   ├── memory.py                # MemoryBackend (default)
│       │   └── redis.py                 # RedisBackend (optional)
│       │
│       ├── security/
│       │   ├── __init__.py
│       │   ├── auth.py                  # AuthBackend Protocol + JWTAuth + APIKeyAuth
│       │   ├── origins.py               # Origin header validation
│       │   └── ratelimit.py             # TokenBucket rate limiter
│       │
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py                  # AdapterBase + helpers
│       │   ├── fastapi.py               # FastAPI adapter
│       │   ├── starlette.py             # Starlette adapter
│       │   ├── django.py                # Django ASGI adapter
│       │   └── quart.py                 # Quart adapter
│       │
│       └── docs/
│           ├── __init__.py
│           ├── engine.py                # reads registry → JSON schema
│           ├── router.py                # HTTP routes for docs UI
│           └── ui/
│               ├── index.html           # Swagger-style shell
│               ├── main.js              # event listing + test panel
│               └── style.css            # styling
│
├── tests/
│   ├── conftest.py                      # shared fixtures
│   ├── unit/
│   │   ├── test_registry.py
│   │   ├── test_router.py
│   │   ├── test_manager.py
│   │   ├── test_rooms.py
│   │   ├── test_session.py
│   │   ├── test_middleware.py
│   │   ├── test_di.py
│   │   ├── test_errors.py
│   │   ├── security/
│   │   │   ├── test_auth.py
│   │   │   ├── test_origins.py
│   │   │   └── test_ratelimit.py
│   │   └── backends/
│   │       ├── test_memory.py
│   │       └── test_redis.py
│   ├── integration/
│   │   ├── test_app.py                  # full SocketApp lifecycle
│   │   ├── test_event_flow.py           # connect → emit → receive
│   │   ├── test_rooms.py                # join → broadcast → leave
│   │   ├── test_auth_flow.py            # auth + expiry + refresh
│   │   └── test_error_handling.py
│   ├── adapters/
│   │   ├── test_fastapi_adapter.py
│   │   └── test_starlette_adapter.py
│   └── client.py                        # TestClient implementation
│
├── docs/                                # MkDocs documentation site
│   ├── index.md                         # Homepage
│   ├── quickstart.md                    # Get running in 5 minutes
│   ├── tutorial/
│   │   ├── index.md
│   │   ├── first-event.md
│   │   ├── payload-validation.md
│   │   ├── rooms.md
│   │   ├── broadcasting.md
│   │   └── auth.md
│   ├── how-to/
│   │   ├── fastapi.md
│   │   ├── django.md
│   │   ├── starlette.md
│   │   ├── redis-backend.md
│   │   ├── dependency-injection.md
│   │   ├── testing.md
│   │   └── deployment.md
│   ├── reference/
│   │   ├── socketapp.md
│   │   ├── connection.md
│   │   ├── rooms.md
│   │   ├── session.md
│   │   ├── security.md
│   │   └── backends.md
│   └── contributing/
│       ├── index.md
│       ├── new-adapter.md
│       └── new-backend.md
│
├── examples/
│   ├── fastapi_chat/                    # Chat room example
│   │   ├── main.py
│   │   └── README.md
│   ├── fastapi_notifications/           # Broadcast to groups
│   │   ├── main.py
│   │   └── README.md
│   └── ai_streaming/                    # Token streaming example
│       ├── main.py
│       └── README.md
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── publish.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   └── adapter_request.yml
│   └── PULL_REQUEST_TEMPLATE.md
│
├── changes/                             # towncrier fragments
│   └── .gitkeep
│
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md
├── ROADMAP.md
├── .pre-commit-config.yaml
├── .gitignore
└── mkdocs.yml
```

---

## 4. Implementation Order

Build in this exact order. Each layer depends on the previous.

```
Step 1   pyproject.toml + _version.py
Step 2   errors.py
Step 3   types.py
Step 4   connection.py
Step 5   backends/base.py + backends/memory.py
Step 6   registry.py
Step 7   session.py
Step 8   security/origins.py + security/ratelimit.py + security/auth.py
Step 9   middleware.py
Step 10  di.py
Step 11  router.py
Step 12  manager.py
Step 13  rooms.py
Step 14  app.py
Step 15  adapters/base.py + adapters/fastapi.py
Step 16  docs/engine.py + docs/router.py + docs/ui/
Step 17  __init__.py (expose public API)
Step 18  tests/ (unit first, then integration)
Step 19  backends/redis.py
Step 20  adapters/starlette.py + adapters/django.py
Step 21  docs/ (MkDocs site)
Step 22  .github/ (CI/CD, templates)
Step 23  examples/
```

---

## 4.5 IP Protection — Applied Before Any Code

Before Cursor writes a single module, these three things must be in place.

### Copyright Header — Every Source File

Every `.py` file inside `src/socketspec/` begins with:

```python
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
```

No exceptions. Every file. Including `__init__.py`, `_version.py`, test files under `tests/`, and adapter files.

### `AUTHORS` file (repo root)

```
SocketSpec was created and is maintained by Laiba Shahab.

Original Author:
  Laiba Shahab <its.laiba.shahab@email.com> — https://github.com/ByteCraftByLaiba
```

### `NOTICE` file (repo root) — required by Apache 2.0

```
SocketSpec
Copyright 2025 Laiba Shahab

This product includes software developed by Laiba Shahab.
https://github.com/ByteCraftByLaiba/socketspec
```

### `CLA.md` (repo root)

```markdown
# SocketSpec Contributor License Agreement

By signing this CLA, you agree to the following terms:

1. **Copyright retained.** You retain copyright ownership of your contributions.

2. **License grant.** You grant Laiba Shahab a perpetual, worldwide, irrevocable,
   non-exclusive, royalty-free license to reproduce, prepare derivative works of,
   publicly display, publicly perform, sublicense, and distribute your contributions
   and any derivative works.

3. **Patent grant.** You grant Laiba Shahab and all recipients of software
   distributed by Laiba Shahab a perpetual, worldwide, irrevocable patent license
   to make, use, sell, offer for sale, import, and otherwise transfer your
   contributions.

4. **Authority.** You confirm you have the legal right to grant this license.

5. **Original work.** You confirm your contribution is your original creation.

Signed electronically via CLA Assistant.
```

---

## 4.6 Coding Standards — Strict and Non-Negotiable

These apply to every file in `src/socketspec/` and `tests/`. No exceptions. No PRs merged that violate these. Cursor must follow every one of these in every file it produces.

---

### File Structure — Every Python File

Every `.py` file follows this exact order, no deviations:

```python
# 1. Copyright header (always first)
# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0
# ...

# 2. Module docstring (always second)
"""
One-line summary of what this module is responsible for.

Longer explanation if needed. What this module owns.
What it does NOT own (to prevent scope creep).
"""

# 3. __future__ imports
from __future__ import annotations

# 4. Standard library imports (alphabetical)
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

# 5. Third-party imports (alphabetical)
import anyio
from pydantic import BaseModel

# 6. Internal imports (absolute, alphabetical)
from socketspec.errors import SocketSpecError
from socketspec.types import ConnectionId, EventName

# 7. Logger (always this exact pattern)
logger = logging.getLogger(__name__)

# 8. Constants (UPPER_SNAKE_CASE)
MAX_RECONNECT_ATTEMPTS = 3

# 9. Type aliases
HandlerFunc = Callable[..., Any]

# 10. Classes and functions
```

---

### Naming Conventions

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

### Type Hints — Mandatory on Everything

```python
# CORRECT — every param and return typed
async def handle_event(
    self,
    conn: Connection,
    raw_message: str | bytes,
) -> None:
    ...

# WRONG — missing types
async def handle_event(self, conn, raw_message):
    ...
```

Rules:
- `mypy --strict` must pass with zero errors on every commit
- Never use bare `Any` in the public API (`src/socketspec/__init__.py` exports)
- `Any` in internal code requires a `# type: ignore[misc]` comment explaining why
- Use `X | None` not `Optional[X]`
- Use `dict`, `list`, `tuple` not `Dict`, `List`, `Tuple`
- Use `type[X]` not `Type[X]`
- All `Protocol` classes must be `@runtime_checkable`

---

### Docstrings — Google Style, Mandatory on All Public Symbols

```python
class ConnectionManager:
    """Owns all live WebSocket connections.

    Single source of truth for connection state. No other module
    stores Connection objects directly. All mutations go through this class.

    Note:
        Thread-safe via asyncio.Lock on all state mutations.
        Does not handle authentication — that happens before connect() is called.
    """

    async def connect(self, conn: Connection) -> None:
        """Register a new connection and inject its send/disconnect capabilities.

        Args:
            conn: The Connection object built by the framework adapter.
                  Must have a valid raw_socket before calling this.

        Raises:
            DuplicateConnectionError: If conn.id already exists (UUID collision,
                                      statistically impossible but handled).
        """
```

Rules:
- Every public class: summary line + extended description + Note section if behaviour is non-obvious
- Every public method: summary line + Args + Returns (if non-None) + Raises (if raises)
- Private methods: docstring only if the logic is non-obvious
- No one-word docstrings (`"""Connect."""` is useless)

---

### Async Patterns — Mandatory

```python
# CORRECT — create_task for fire-and-forget
asyncio.create_task(self._run_handler(conn, definition, payload))

# WRONG — bare coroutine not awaited silently
self._run_handler(conn, definition, payload)  # this does nothing

# CORRECT — lock always via async with
async with self._lock:
    self._connections[conn.id] = conn

# WRONG — manual acquire/release
await self._lock.acquire()
self._connections[conn.id] = conn
self._lock.release()  # won't run if exception thrown

# CORRECT — CancelledError always re-raised in tasks
async def _session_loop(self, conn: Connection) -> None:
    try:
        await asyncio.sleep(self._config.heartbeat_interval)
    except asyncio.CancelledError:
        raise  # always re-raise, never swallow

# WRONG — swallowing CancelledError
    except asyncio.CancelledError:
        pass  # task will hang, never clean up
```

Rules:
- Never use `asyncio.run()` inside an async context
- Never call a coroutine without `await` or `asyncio.create_task()`
- Always `raise` `asyncio.CancelledError` — never swallow it
- Always use `async with` for locks — never manual acquire/release
- Use `anyio` primitives where possible for trio compatibility
- Long-running tasks always handle `CancelledError` for clean shutdown

---

### Error Handling — Strict Pattern

```python
# CORRECT — specific exception, logged with context
try:
    await conn.raw_socket.send_json(message)
except WebSocketDisconnect:
    logger.debug("Connection %s closed before send", conn.id)
except Exception:
    logger.error("Unexpected send failure for %s", conn.id, exc_info=True)

# WRONG — bare except
try:
    await conn.raw_socket.send_json(message)
except:  # catches KeyboardInterrupt, SystemExit, everything
    pass

# WRONG — catching too broadly and hiding errors
try:
    await conn.raw_socket.send_json(message)
except Exception:
    pass  # silent failure, impossible to debug
```

Rules:
- Never use bare `except:` — always `except SpecificException:`
- Never catch `BaseException` (it catches `KeyboardInterrupt` and `SystemExit`)
- Never `pass` on an exception without a `logger.debug/warning/error` call
- Every unexpected exception logged at `ERROR` level with `exc_info=True`
- All custom exceptions must inherit from `SocketSpecError`
- Exceptions raised from public API must be documented in the docstring `Raises:` section

---

### Logging — Standard Pattern

```python
# Module-level logger — always this pattern, never deviate
logger = logging.getLogger(__name__)

# Correct level usage
logger.debug("Connection %s received event: %s", conn.id, event)  # trace info
logger.info("Connection %s established", conn.id)                  # lifecycle
logger.warning("Redis unavailable, falling back to memory", )      # degraded
logger.error("Handler failed for event %s", event, exc_info=True)  # failure

# WRONG — print statements in library code
print(f"Connection {conn.id} connected")  # never in library code

# WRONG — f-strings in log calls (evaluates even when log level disabled)
logger.debug(f"Connection {conn.id} received {event}")  # use % formatting
```

Rules:
- `logging.getLogger(__name__)` in every module — no global loggers
- Never use `print()` in library code — ever
- Use `%` style formatting in log calls, not f-strings (performance)
- DEBUG: trace-level internal state
- INFO: connection lifecycle (connect, disconnect, room join/leave)
- WARNING: degraded state (Redis fallback, rate limit approaching)
- ERROR: failures (handler crash, auth failure, send failure)
- Never log secrets, tokens, or full payloads at INFO or above

---

### Constants and Magic Strings — Zero Tolerance

```python
# CORRECT — named constant, one place to change
BROADCAST_CHUNK_SIZE = 500
RESERVED_EVENTS: frozenset[str] = frozenset({
    "__connect__",
    "__error__",
    "__ping__",
})

# WRONG — magic number buried in code
async def _broadcast(self, ...):
    for chunk in self._chunks(members, 500):  # what is 500? where is it defined?
        ...

# WRONG — magic string
if event.startswith("__"):  # fragile, inconsistent
    raise ReservedEventNameError(...)
```

Rules:
- All numeric limits defined as module-level constants with a comment explaining the value
- All reserved event names in one `RESERVED_EVENTS` frozenset in `errors.py`
- All error code strings in one `ErrorCode` enum or frozenset in `errors.py`
- No string literals repeated more than once — extract to a constant

---

### Imports — Absolute Only in Public API

```python
# CORRECT — absolute imports everywhere
from socketspec.connection import Connection
from socketspec.errors import SocketSpecError

# WRONG — relative imports in src/socketspec/ files
from .connection import Connection
from ..errors import SocketSpecError
```

Rules:
- No relative imports anywhere in `src/socketspec/`
- No circular imports — enforced by the build order in Section 4
- `__init__.py` is the only file that re-exports symbols
- Test files use absolute imports: `from socketspec.connection import Connection`

---

### Test Standards

```python
# CORRECT test naming — describes what, when, and expected outcome
async def test_connect_rejects_origin_not_in_allowed_list() -> None: ...
async def test_broadcast_skips_disconnected_member_silently() -> None: ...
async def test_registry_raises_on_duplicate_event_name() -> None: ...

# WRONG — vague names
async def test_connect() -> None: ...
async def test_broadcast() -> None: ...

# CORRECT — one behaviour per test
async def test_rate_limiter_blocks_after_limit_exceeded() -> None:
    limiter = TokenBucket(RateLimit(events=2, per_seconds=60))
    assert await limiter.consume("conn_1") is True
    assert await limiter.consume("conn_1") is True
    assert await limiter.consume("conn_1") is False  # third is blocked

# WRONG — multiple unrelated behaviours in one test
async def test_rate_limiter() -> None:
    # tests connect, consume, refill, remove — too broad
```

Rules:
- Test function names: `test_<what>_<condition>_<expected_outcome>`
- One primary assertion per test
- Each test is fully independent — no shared mutable state between tests
- All fixtures in `conftest.py` — never in test files
- No `time.sleep()` in tests — use `anyio.sleep()` or mock time
- `asyncio_mode = "auto"` already set — no `@pytest.mark.asyncio` needed on individual tests
- Mock at the boundary — mock `BackendAdapter`, not internal methods

---

### Git Commit Messages — Conventional Commits

```
feat(registry): add deprecated flag to EventDefinition
fix(manager): prevent duplicate connection on UUID collision
docs(readme): add Redis backend example
test(rooms): add broadcast to non-existent room coverage
refactor(router): extract payload size check to helper
chore(ci): add Python 3.13 to test matrix
security(auth): validate algorithm in JWTAuth to prevent none attack
adapter(django): add Django ASGI adapter
```

Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `security`, `adapter`, `backend`

Rules:
- Present tense, lowercase, no period at end
- Scope is the module or component affected
- Breaking changes: add `!` after type — `feat(app)!: rename SocketApp.serve() to mount()`
- Every commit must pass CI before merge to main

---

## 4.7 Context File System — AI Traceability

Every version of SocketSpec maintains a versioned system context file. This file is the complete understanding of the system — architecture, files, flows, decisions — written so that an AI tool picking up the project mid-development can understand everything without reading the code.

### File Location

```
.context/
├── CODING_STANDARDS.md        ← extracted from this plan, rarely changes
├── SYSTEM_CURRENT.md          ← always the latest version (updated per PR)
├── v0.1.0/
│   └── SYSTEM.md              ← snapshot at v0.1.0 release
├── v0.2.0/
│   └── SYSTEM.md              ← snapshot at v0.2.0 release
└── v0.3.0/
    └── SYSTEM.md
```

### When to Update SYSTEM_CURRENT.md

A PR must update `SYSTEM_CURRENT.md` if it does any of the following:
- Adds a new module or file to `src/socketspec/`
- Changes a public API signature
- Changes how two modules interact
- Adds or removes a system invariant
- Makes a technical decision that affects architecture
- Adds a new adapter or backend

If a PR only fixes a bug within existing behaviour without changing structure — no update needed.

### When to Create a Version Snapshot

When a version tag is pushed (`v0.2.0`, `v0.3.0`, etc.):
1. Copy `SYSTEM_CURRENT.md` to `.context/vX.Y.Z/SYSTEM.md`
2. Add `## Changes from vX.Y.(Z-1)` section at the top of the snapshot
3. Commit with message: `chore(context): snapshot SYSTEM.md for vX.Y.Z`

### What SYSTEM_CURRENT.md Must Always Contain

1. **System overview** — one paragraph, what SocketSpec is and what it owns
2. **Core invariants** — the rules that must never be broken
3. **Module map** — every file in `src/socketspec/`, its purpose, its public API, what it does NOT own
4. **Data flows** — step-by-step for: connect, emit event, broadcast, disconnect, error
5. **Dependency graph** — which modules import which (prevents circular imports)
6. **Active decisions** — key technical decisions and why they were made
7. **Known limitations** — what the system intentionally does not handle
8. **Version** — which version this context represents

### How an AI Tool Uses This

When an AI tool (Cursor, Claude, or any other) is brought into the project:
1. Read `.context/SYSTEM_CURRENT.md` first — full system understanding
2. Read `.context/CODING_STANDARDS.md` second — how code must be written
3. Then read the specific file(s) relevant to the task
4. Never make changes that violate the invariants in SYSTEM_CURRENT.md
5. If changes affect the system structure, update SYSTEM_CURRENT.md in the same PR

---

### 5.1 `errors.py`

All custom exceptions. Users import these for handling.

```python
class SocketSpecError(Exception):
    """Base exception for all SocketSpec errors."""

class DuplicateEventError(SocketSpecError):
    """Raised at startup when two handlers register the same event name."""

class ReservedEventNameError(SocketSpecError):
    """Raised when user tries to register a reserved system event name."""

class ConnectionNotFoundError(SocketSpecError):
    """Raised when an operation targets a connection_id that doesn't exist."""

class RoomNotFoundError(SocketSpecError):
    """Raised when broadcasting to a room that doesn't exist."""

class AuthenticationError(SocketSpecError):
    """Raised when authentication fails during connect."""

class PayloadTooLargeError(SocketSpecError):
    """Raised when incoming payload exceeds max_payload_size."""

class RoomPermissionError(SocketSpecError):
    """Raised when a room guard returns False."""

class StartupValidationError(SocketSpecError):
    """Raised during startup validation before server accepts connections."""
```

**Reserved system event names** (raise `ReservedEventNameError` if user tries to register):
```python
RESERVED_EVENTS = frozenset({
    "__connect__",
    "__disconnect__",
    "__error__",
    "__ping__",
    "__pong__",
    "__auth_expiring__",
    "__session_expiring__",
    "__idle_warning__",
    "__server_shutdown__",
    "__refresh_auth__",
})
```

---

### 5.2 `types.py`

Shared type aliases used across modules. Keep this minimal.

```python
from typing import Any, Callable, Awaitable
from pydantic import BaseModel

EventName = str
ConnectionId = str
RoomName = str
Namespace = str
HandlerFunc = Callable[..., Awaitable[None]]
PayloadDict = dict[str, Any]

# The standard error envelope shape — used everywhere
ErrorCode = str
```

---

### 5.3 `connection.py`

The `Connection` object is the primary thing every handler receives.

```python
@dataclass
class Identity:
    user_id: str | None = None
    scopes: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    raw_token: str | None = None

@dataclass
class SessionInfo:
    started_at: datetime
    expires_at: datetime | None        # from max_duration
    token_expires_at: datetime | None  # from JWT exp claim

@dataclass
class Connection:
    id: ConnectionId                   # UUID4, set at connect
    raw_socket: Any                    # raw WS object from framework adapter
    identity: Identity
    session: SessionInfo
    connected_at: datetime
    last_active: datetime              # updated on every incoming event
    rooms: set[RoomName]               # rooms this connection is in
    metadata: dict[str, Any]           # user-settable, persists per connection
    headers: dict[str, str]            # HTTP upgrade headers
    query_params: dict[str, str]       # HTTP upgrade query params
    namespace: str = "/"

    async def emit(self, event: EventName, payload: Any) -> None:
        """Emit an event directly to this connection."""
        # implemented by ConnectionManager injecting send capability
        ...

    async def disconnect(self, reason: str = "server_close") -> None:
        """Forcibly close this connection."""
        ...
```

**Implementation note:** `emit` and `disconnect` are set by `ConnectionManager` during `connect()` as bound callables. `Connection` itself is a pure data class — it does not import `ConnectionManager` (avoids circular imports).

---

### 5.4 `registry.py`

The central event registry. Everything that exists in the system is known here.

```python
@dataclass
class Emits:
    """Metadata describing an event this handler may emit back to the sender."""
    event: EventName
    model: type[BaseModel] | None = None
    description: str = ""

@dataclass
class Broadcasts:
    """Metadata describing an event this handler may broadcast to a room."""
    event: EventName
    room: str                           # supports "{variable}" patterns
    model: type[BaseModel] | None = None
    description: str = ""

@dataclass
class EventDefinition:
    name: EventName
    namespace: Namespace
    handler: HandlerFunc
    payload_model: type[BaseModel] | None
    emits: list[Emits]                  # docs metadata only
    broadcasts: list[Broadcasts]        # docs metadata only
    description: str
    tags: list[str]
    ordered: bool                       # serialize events per connection
    executor: bool                      # run in threadpool
    deprecated: bool = False
    dependencies: list[Any] = field(default_factory=list)  # Depends() list

class EventRegistry:
    def __init__(self) -> None:
        self._events: dict[tuple[Namespace, EventName], EventDefinition] = {}
        self._validated: bool = False

    def register(self, definition: EventDefinition) -> None:
        """Register an event. Raises on duplicate or reserved names."""
        if definition.name in RESERVED_EVENTS:
            raise ReservedEventNameError(f"'{definition.name}' is a reserved event name.")
        key = (definition.namespace, definition.name)
        if key in self._events:
            raise DuplicateEventError(
                f"Event '{definition.name}' already registered in namespace '{definition.namespace}'."
            )
        self._events[key] = definition

    def get(self, namespace: Namespace, name: EventName) -> EventDefinition | None:
        return self._events.get((namespace, name))

    def all(self) -> list[EventDefinition]:
        return list(self._events.values())

    def validate(self) -> None:
        """Run all startup validations. Called once before server starts."""
        self._validated = True
        # Future: additional cross-event validations here
```

---

### 5.5 `backends/base.py`

The Protocol that both MemoryBackend and RedisBackend implement.

```python
from typing import Protocol, runtime_checkable, Callable, Awaitable

@runtime_checkable
class BackendAdapter(Protocol):
    async def store_connection(self, id: ConnectionId, meta: dict) -> None: ...
    async def remove_connection(self, id: ConnectionId) -> None: ...
    async def connection_exists(self, id: ConnectionId) -> bool: ...
    async def get_room_members(self, room: RoomName) -> list[ConnectionId]: ...
    async def add_to_room(self, id: ConnectionId, room: RoomName) -> None: ...
    async def remove_from_room(self, id: ConnectionId, room: RoomName) -> None: ...
    async def get_connection_rooms(self, id: ConnectionId) -> list[RoomName]: ...
    async def publish(self, channel: str, message: dict) -> None: ...
    async def subscribe(self, channel: str, callback: Callable[[dict], Awaitable[None]]) -> None: ...
    async def unsubscribe(self, channel: str) -> None: ...
    async def close(self) -> None: ...
```

---

### 5.6 `backends/memory.py`

Default backend. Single process. Thread-safe via `asyncio.Lock`.

```python
class MemoryBackend:
    def __init__(self) -> None:
        self._connections: dict[ConnectionId, dict] = {}
        self._rooms: dict[RoomName, set[ConnectionId]] = {}
        self._conn_rooms: dict[ConnectionId, set[RoomName]] = {}
        self._subscribers: dict[str, list[Callable]] = {}
        self._lock = asyncio.Lock()

    async def store_connection(self, id: ConnectionId, meta: dict) -> None:
        async with self._lock:
            self._connections[id] = meta
            self._conn_rooms[id] = set()

    async def remove_connection(self, id: ConnectionId) -> None:
        async with self._lock:
            self._connections.pop(id, None)
            # Clean up room membership
            rooms = self._conn_rooms.pop(id, set())
            for room in rooms:
                self._rooms.get(room, set()).discard(id)
                if not self._rooms.get(room):
                    self._rooms.pop(room, None)

    async def get_room_members(self, room: RoomName) -> list[ConnectionId]:
        async with self._lock:
            return list(self._rooms.get(room, set()))

    async def add_to_room(self, id: ConnectionId, room: RoomName) -> None:
        async with self._lock:
            if room not in self._rooms:
                self._rooms[room] = set()
            self._rooms[room].add(id)
            self._conn_rooms.setdefault(id, set()).add(room)

    async def remove_from_room(self, id: ConnectionId, room: RoomName) -> None:
        async with self._lock:
            self._rooms.get(room, set()).discard(id)
            if not self._rooms.get(room):
                self._rooms.pop(room, None)
            self._conn_rooms.get(id, set()).discard(room)

    async def get_connection_rooms(self, id: ConnectionId) -> list[RoomName]:
        async with self._lock:
            return list(self._conn_rooms.get(id, set()))

    async def publish(self, channel: str, message: dict) -> None:
        # In-memory: deliver directly to subscribers
        for callback in self._subscribers.get(channel, []):
            await callback(message)

    async def subscribe(self, channel: str, callback: Callable) -> None:
        self._subscribers.setdefault(channel, []).append(callback)

    async def unsubscribe(self, channel: str) -> None:
        self._subscribers.pop(channel, None)

    async def connection_exists(self, id: ConnectionId) -> bool:
        async with self._lock:
            return id in self._connections

    async def close(self) -> None:
        async with self._lock:
            self._connections.clear()
            self._rooms.clear()
            self._conn_rooms.clear()
            self._subscribers.clear()
```

---

### 5.7 `session.py`

Session config and TTL management.

```python
@dataclass
class SessionConfig:
    max_duration: int = 7200           # seconds, 0 = no limit
    idle_timeout: int = 300            # seconds, 0 = no limit
    heartbeat_interval: int = 25       # seconds between server pings
    heartbeat_timeout: int = 10        # seconds to wait for pong
    token_refresh_window: int = 60     # seconds before JWT expiry to warn client

class SessionManager:
    """Manages heartbeat tasks and TTL enforcement per connection."""

    def __init__(self, config: SessionConfig) -> None:
        self._config = config
        self._tasks: dict[ConnectionId, asyncio.Task] = {}

    async def start(self, conn: Connection) -> None:
        """Start heartbeat + idle + max_duration tasks for a connection."""
        task = asyncio.create_task(self._session_loop(conn))
        self._tasks[conn.id] = task

    async def stop(self, conn_id: ConnectionId) -> None:
        """Cancel all tasks for a connection on disconnect."""
        task = self._tasks.pop(conn_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def touch(self, conn: Connection) -> None:
        """Update last_active on every incoming event."""
        conn.last_active = datetime.utcnow()

    async def _session_loop(self, conn: Connection) -> None:
        """Main session management loop for one connection."""
        # Implementation handles:
        # 1. Periodic ping sending every heartbeat_interval
        # 2. Pong timeout detection (disconnect if no pong in heartbeat_timeout)
        # 3. Idle timeout (disconnect if last_active is stale)
        # 4. Max duration enforcement
        # 5. Token expiry warning
```

---

### 5.8 `security/auth.py`

Auth protocol plus two built-in implementations.

```python
@dataclass
class Identity:
    user_id: str | None = None
    scopes: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    raw_token: str | None = None
    token_expires_at: datetime | None = None

class AuthBackend(Protocol):
    async def authenticate(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Identity | None:
        """Return Identity if auth passes, None to reject connection."""
        ...

class JWTAuth:
    def __init__(self, secret: str, algorithm: str = "HS256", header: str = "authorization") -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._header = header

    async def authenticate(self, headers: dict, query_params: dict) -> Identity | None:
        # Check Authorization header or ?token= query param
        # Decode JWT, extract claims, return Identity
        # Return None on any failure (expired, invalid, missing)
        ...

class APIKeyAuth:
    def __init__(self, api_key: str, header: str = "x-api-key") -> None:
        self._api_key = api_key
        self._header = header

    async def authenticate(self, headers: dict, query_params: dict) -> Identity | None:
        key = headers.get(self._header) or query_params.get("api_key")
        if key == self._api_key:
            return Identity()
        return None
```

---

### 5.9 `security/origins.py`

Origin validation during HTTP upgrade.

```python
class OriginValidator:
    def __init__(self, allowed_origins: list[str]) -> None:
        # "*" means allow all (dev mode)
        self._allowed = set(allowed_origins)
        self._allow_all = "*" in allowed_origins

    def is_allowed(self, origin: str | None) -> bool:
        if self._allow_all:
            return True
        if origin is None:
            return False                # no origin header — reject
        return origin in self._allowed
```

---

### 5.10 `security/ratelimit.py`

Token bucket rate limiter, per connection.

```python
@dataclass
class RateLimit:
    events: int = 100                  # max events
    per_seconds: int = 60              # per time window

class TokenBucket:
    """Per-connection token bucket. Thread-safe via asyncio.Lock."""

    def __init__(self, config: RateLimit) -> None:
        self._max = config.events
        self._refill_rate = config.events / config.per_seconds
        self._buckets: dict[ConnectionId, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, conn_id: ConnectionId) -> bool:
        """Returns True if event is allowed, False if rate limit exceeded."""
        async with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(conn_id, (self._max, now))
            elapsed = now - last_refill
            tokens = min(self._max, tokens + elapsed * self._refill_rate)
            if tokens < 1:
                self._buckets[conn_id] = (tokens, now)
                return False
            self._buckets[conn_id] = (tokens - 1, now)
            return True

    async def remove(self, conn_id: ConnectionId) -> None:
        async with self._lock:
            self._buckets.pop(conn_id, None)
```

---

### 5.11 `middleware.py`

Middleware chain compiled once at startup.

```python
MiddlewareFunc = Callable[[Connection, EventName, PayloadDict, Callable], Awaitable[None]]

class MiddlewareChain:
    def __init__(self, middlewares: list[MiddlewareFunc]) -> None:
        self._chain = middlewares

    def compile(self, final_handler: Callable) -> Callable:
        """
        Build the call chain at startup.
        Returns a single callable: call(conn, event, payload) → runs full chain.
        Compiles once. Zero overhead per-event beyond actual function calls.
        """
        handler = final_handler
        for middleware in reversed(self._chain):
            handler = self._wrap(middleware, handler)
        return handler

    def _wrap(self, middleware: MiddlewareFunc, next_handler: Callable) -> Callable:
        async def wrapped(conn: Connection, event: EventName, payload: PayloadDict) -> None:
            await middleware(conn, event, payload, lambda: next_handler(conn, event, payload))
        return wrapped
```

---

### 5.12 `di.py`

Dependency injection resolver. Mirrors FastAPI's Depends mechanism.

```python
class Depends:
    def __init__(self, dependency: Callable) -> None:
        self.dependency = dependency

class DependencyResolver:
    async def resolve(self, handler: Callable, conn: Connection) -> dict[str, Any]:
        """
        Inspect handler signature.
        Find all parameters with Depends() defaults.
        Resolve dependency tree (supports chained dependencies).
        Return dict of resolved values to inject.
        """
        import inspect
        sig = inspect.signature(handler)
        resolved = {}
        for name, param in sig.parameters.items():
            if isinstance(param.default, Depends):
                dep_func = param.default.dependency
                # Recursively resolve nested Depends
                dep_args = await self.resolve(dep_func, conn)
                # Call the dependency (supports yield for cleanup)
                result = await dep_func(conn, **dep_args)
                resolved[name] = result
        return resolved
```

**Note:** Yield-based dependencies (like `get_db()`) need a cleanup step. Track generators and close them after the handler completes. Implementation should use `contextlib.asynccontextmanager` pattern internally.

---

### 5.13 `router.py`

Routes incoming events to the correct handler.

```python
class EventRouter:
    def __init__(
        self,
        registry: EventRegistry,
        di_resolver: DependencyResolver,
    ) -> None:
        self._registry = registry
        self._di_resolver = di_resolver
        # Per-connection ordered queues (for ordered=True events)
        self._queues: dict[ConnectionId, asyncio.Queue] = {}

    async def dispatch(
        self,
        conn: Connection,
        event: EventName,
        payload: PayloadDict,
    ) -> None:
        definition = self._registry.get(conn.namespace, event)
        if definition is None:
            await self._emit_error(conn, "UNKNOWN_EVENT", event, f"Unknown event: {event}")
            return

        # Validate payload with Pydantic
        validated = await self._validate(conn, definition, payload)
        if validated is None:
            return  # error already emitted

        if definition.ordered:
            await self._dispatch_ordered(conn, definition, validated)
        else:
            asyncio.create_task(self._run_handler(conn, definition, validated))

    async def _validate(self, conn, definition, payload):
        if definition.payload_model is None:
            return payload
        try:
            return definition.payload_model.model_validate(payload)
        except ValidationError as e:
            await self._emit_error(conn, "VALIDATION_ERROR", definition.name, str(e), e.errors())
            return None

    async def _run_handler(self, conn, definition, payload):
        try:
            injected = await self._di_resolver.resolve(definition.handler, conn)
            if definition.executor:
                await anyio.to_thread.run_sync(
                    lambda: asyncio.run(definition.handler(conn, payload, **injected))
                )
            else:
                await definition.handler(conn, payload, **injected)
        except Exception as e:
            await self._emit_error(conn, "HANDLER_ERROR", definition.name, str(e))

    async def _dispatch_ordered(self, conn, definition, payload):
        if conn.id not in self._queues:
            self._queues[conn.id] = asyncio.Queue()
            asyncio.create_task(self._process_queue(conn))
        await self._queues[conn.id].put((definition, payload))

    async def _process_queue(self, conn):
        queue = self._queues[conn.id]
        while True:
            definition, payload = await queue.get()
            await self._run_handler(conn, definition, payload)
            queue.task_done()

    async def _emit_error(self, conn, code, event, message, details=None):
        import uuid
        error_payload = {
            "event": "__error__",
            "payload": {
                "code": code,
                "event": event,
                "message": message,
                "request_id": str(uuid.uuid4()),
                "details": details or {},
            }
        }
        await conn.emit("__error__", error_payload["payload"])
```

---

### 5.14 `manager.py`

Single owner of all live WebSocket connections.

```python
class ConnectionManager:
    def __init__(self, backend: BackendAdapter) -> None:
        self._backend = backend
        self._connections: dict[ConnectionId, Connection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conn: Connection) -> None:
        async with self._lock:
            self._connections[conn.id] = conn
        await self._backend.store_connection(conn.id, {
            "user_id": conn.identity.user_id,
            "namespace": conn.namespace,
            "connected_at": conn.connected_at.isoformat(),
        })
        # Inject send/disconnect capabilities into the Connection object
        conn.emit = self._make_emitter(conn)
        conn.disconnect = self._make_disconnector(conn)

    async def disconnect(self, conn: Connection) -> None:
        async with self._lock:
            self._connections.pop(conn.id, None)
        await self._backend.remove_connection(conn.id)

    async def get(self, conn_id: ConnectionId) -> Connection | None:
        async with self._lock:
            return self._connections.get(conn_id)

    async def all(self) -> list[Connection]:
        async with self._lock:
            return list(self._connections.values())

    async def send(self, conn_id: ConnectionId, event: EventName, payload: Any) -> None:
        conn = await self.get(conn_id)
        if conn is None:
            return
        message = {"event": event, "payload": payload}
        try:
            await conn.raw_socket.send_json(message)
        except Exception:
            # Connection is dead — don't propagate, just log
            pass

    def _make_emitter(self, conn: Connection) -> Callable:
        async def emit(event: EventName, payload: Any) -> None:
            await self.send(conn.id, event, payload)
        return emit

    def _make_disconnector(self, conn: Connection) -> Callable:
        async def disconnect(reason: str = "server_close") -> None:
            await self.disconnect(conn)
        return disconnect
```

---

### 5.15 `rooms.py`

Room management on top of the backend.

```python
BROADCAST_CHUNK_SIZE = 500

class RoomManager:
    def __init__(self, backend: BackendAdapter, manager: ConnectionManager) -> None:
        self._backend = backend
        self._manager = manager
        self._guards: dict[str, Callable] = {}         # pattern → guard func
        self._static_rooms: set[RoomName] = set()

    def register_guard(self, pattern: str, guard: Callable) -> None:
        self._guards[pattern] = guard

    def register_static(self, room: RoomName) -> None:
        self._static_rooms.add(room)

    async def join(self, conn: Connection, room: RoomName) -> None:
        # Check guard if pattern matches
        guard = self._match_guard(room)
        if guard:
            variables = self._extract_variables(guard._pattern, room)
            allowed = await guard(conn, **variables)
            if not allowed:
                raise RoomPermissionError(f"Access denied to room '{room}'")
        await self._backend.add_to_room(conn.id, room)
        conn.rooms.add(room)

    async def leave(self, conn: Connection, room: RoomName) -> None:
        await self._backend.remove_from_room(conn.id, room)
        conn.rooms.discard(room)

    async def broadcast(self, room: RoomName, event: EventName, payload: Any) -> None:
        member_ids = await self._backend.get_room_members(room)
        if not member_ids:
            return
        # Chunk large rooms to avoid memory spikes
        for chunk in self._chunks(member_ids, BROADCAST_CHUNK_SIZE):
            await asyncio.gather(*[
                self._safe_send(conn_id, event, payload)
                for conn_id in chunk
            ])

    async def broadcast_all(self, event: EventName, payload: Any) -> None:
        all_conns = await self._manager.all()
        for chunk in self._chunks([c.id for c in all_conns], BROADCAST_CHUNK_SIZE):
            await asyncio.gather(*[
                self._safe_send(conn_id, event, payload)
                for conn_id in chunk
            ])

    async def broadcast_except(self, exclude_id: ConnectionId, event: EventName, payload: Any) -> None:
        all_conns = await self._manager.all()
        targets = [c.id for c in all_conns if c.id != exclude_id]
        for chunk in self._chunks(targets, BROADCAST_CHUNK_SIZE):
            await asyncio.gather(*[
                self._safe_send(conn_id, event, payload)
                for conn_id in chunk
            ])

    async def members(self, room: RoomName) -> list[Connection]:
        ids = await self._backend.get_room_members(room)
        conns = [await self._manager.get(id) for id in ids]
        return [c for c in conns if c is not None]

    async def _safe_send(self, conn_id: ConnectionId, event: EventName, payload: Any) -> None:
        try:
            await self._manager.send(conn_id, event, payload)
        except Exception:
            pass  # dead connection — skip silently

    @staticmethod
    def _chunks(lst: list, size: int):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]
```

---

### 5.16 `app.py`

The main `SocketApp` class. This is what users import and configure.

```python
class SocketApp:
    def __init__(
        self,
        *,
        docs: bool = False,
        docs_url: str = "/socket-docs",
        docs_access_token: str | None = None,
        auth: AuthBackend | None = None,
        backend: Literal["memory", "redis"] | BackendAdapter = "memory",
        allowed_origins: list[str] = ["*"],
        max_payload_size: int = 65_536,         # 64KB
        rate_limit: RateLimit | None = None,
        session: SessionConfig | None = None,
        rooms: list[Room] = [],
        namespace: str = "/",
    ) -> None:
        # Build internal components
        self._registry = EventRegistry()
        self._backend = self._build_backend(backend)
        self._manager = ConnectionManager(self._backend)
        self._session_mgr = SessionManager(session or SessionConfig())
        self._origin_validator = OriginValidator(allowed_origins)
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
        self._lifecycle_hooks: dict[str, list[Callable]] = {
            "connect": [], "disconnect": [], "error": [],
            "room_join": [], "room_leave": [],
        }

    # ── Decorator API ────────────────────────────────────────

    def on(
        self,
        event: EventName,
        *,
        description: str = "",
        tags: list[str] = [],
        emits: list[Emits] = [],
        broadcasts: list[Broadcasts] = [],
        ordered: bool = False,
        executor: bool = False,
        deprecated: bool = False,
    ) -> Callable:
        """Register an event handler."""
        def decorator(func: HandlerFunc) -> HandlerFunc:
            definition = EventDefinition(
                name=event,
                namespace=self._namespace,
                handler=func,
                payload_model=self._infer_payload_model(func),
                emits=emits,
                broadcasts=broadcasts,
                description=description,
                tags=tags,
                ordered=ordered,
                executor=executor,
                deprecated=deprecated,
            )
            self._registry.register(definition)
            return func
        return decorator

    def middleware(self, func: MiddlewareFunc) -> MiddlewareFunc:
        """Register a middleware function."""
        self._middlewares.append(func)
        return func

    def on_connect(self, func: Callable) -> Callable:
        self._lifecycle_hooks["connect"].append(func)
        return func

    def on_disconnect(self, func: Callable) -> Callable:
        self._lifecycle_hooks["disconnect"].append(func)
        return func

    def on_error(self, func: Callable) -> Callable:
        self._lifecycle_hooks["error"].append(func)
        return func

    def on_room_join(self, func: Callable) -> Callable:
        self._lifecycle_hooks["room_join"].append(func)
        return func

    def on_room_leave(self, func: Callable) -> Callable:
        self._lifecycle_hooks["room_leave"].append(func)
        return func

    def room_guard(self, pattern: str) -> Callable:
        """Protect a room pattern with a permission function."""
        def decorator(func: Callable) -> Callable:
            func._pattern = pattern
            self.rooms.register_guard(pattern, func)
            return func
        return decorator

    # ── Connection lifecycle ────────────────────────────────

    async def handle_connect(self, raw_socket: Any, headers: dict, query_params: dict) -> Connection | None:
        """Called by framework adapters on new WebSocket connection."""
        # 1. Origin check
        origin = headers.get("origin")
        if not self._origin_validator.is_allowed(origin):
            await raw_socket.close(code=403)
            return None
        # 2. Auth
        identity = Identity()
        if self._auth:
            identity = await self._auth.authenticate(headers, query_params)
            if identity is None:
                await self._emit_raw(raw_socket, "__error__", {"code": "AUTH_ERROR"})
                await raw_socket.close(code=4001)
                return None
        # 3. Build connection
        conn = self._build_connection(raw_socket, identity, headers, query_params)
        await self._manager.connect(conn)
        await self._session_mgr.start(conn)
        # 4. Run on_connect hooks
        for hook in self._lifecycle_hooks["connect"]:
            await hook(conn)
        return conn

    async def handle_event(self, conn: Connection, raw_message: str | bytes) -> None:
        """Called by framework adapters for every incoming message."""
        # 1. Payload size check
        size = len(raw_message) if isinstance(raw_message, bytes) else len(raw_message.encode())
        if size > self._max_payload_size:
            await conn.emit("__error__", {"code": "PAYLOAD_TOO_LARGE"})
            return
        # 2. Parse JSON
        try:
            data = json.loads(raw_message)
            event = data["event"]
            payload = data.get("payload", {})
        except (json.JSONDecodeError, KeyError):
            await conn.emit("__error__", {"code": "VALIDATION_ERROR", "message": "Invalid message format"})
            return
        # 3. Rate limit
        if self._rate_limiter:
            allowed = await self._rate_limiter.consume(conn.id)
            if not allowed:
                await conn.emit("__error__", {"code": "RATE_LIMIT_ERROR"})
                return
        # 4. Touch session (update last_active)
        await self._session_mgr.touch(conn)
        # 5. Middleware chain → router
        await self._compiled_chain(conn, event, payload)

    async def handle_disconnect(self, conn: Connection, reason: str = "client_close") -> None:
        """Called by framework adapters on connection close."""
        await self._session_mgr.stop(conn.id)
        for room in list(conn.rooms):
            await self.rooms.leave(conn, room)
            for hook in self._lifecycle_hooks["room_leave"]:
                await hook(conn, room)
        await self._manager.disconnect(conn)
        for hook in self._lifecycle_hooks["disconnect"]:
            await hook(conn, reason)
        if self._rate_limiter:
            await self._rate_limiter.remove(conn.id)

    # ── Startup ─────────────────────────────────────────────

    def _startup_validate(self) -> None:
        """Run all validations. Called before first connection accepted."""
        self._registry.validate()
        # Compile middleware chain once
        self._compiled_chain = MiddlewareChain(self._middlewares).compile(
            self._router.dispatch
        )

    # ── Helpers ─────────────────────────────────────────────

    def _infer_payload_model(self, func: Callable) -> type[BaseModel] | None:
        """Extract Pydantic model from second parameter type hint."""
        import inspect
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        # params[0] = conn: Connection, params[1] = payload: SomeModel
        if len(params) >= 2:
            annotation = params[1].annotation
            if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
                return annotation
        return None
```

---

### 5.17 `adapters/fastapi.py`

Thin adapter. Only job: translate FastAPI WebSocket to Connection.

```python
def mount(socket_app: SocketApp, app: FastAPI, *, path: str = "/ws") -> None:
    """Mount SocketApp into a FastAPI application."""

    @app.on_event("startup")
    async def startup():
        socket_app._startup_validate()

    @app.on_event("shutdown")
    async def shutdown():
        await socket_app._graceful_shutdown()

    @app.websocket(path)
    async def websocket_endpoint(websocket: WebSocket):
        # Extract headers and query params from FastAPI WebSocket
        headers = dict(websocket.headers)
        query_params = dict(websocket.query_params)

        # Check origin before accepting (HTTP upgrade phase)
        origin = headers.get("origin")
        if not socket_app._origin_validator.is_allowed(origin):
            await websocket.close(code=1008)
            return

        await websocket.accept()

        conn = await socket_app.handle_connect(
            raw_socket=FastAPISocketWrapper(websocket),
            headers=headers,
            query_params=query_params,
        )
        if conn is None:
            return

        try:
            while True:
                data = await websocket.receive_text()
                await socket_app.handle_event(conn, data)
        except WebSocketDisconnect as e:
            await socket_app.handle_disconnect(conn, reason=str(e.code))

    # Mount docs UI if enabled
    if socket_app._docs:
        _mount_docs(socket_app, app)


class FastAPISocketWrapper:
    """Normalizes FastAPI WebSocket to what ConnectionManager expects."""
    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def send_json(self, data: dict) -> None:
        await self._ws.send_json(data)

    async def close(self, code: int = 1000) -> None:
        await self._ws.close(code=code)
```

---

### 5.18 `docs/engine.py`

Reads the EventRegistry and produces the JSON schema the UI needs.

```python
class DocsEngine:
    def __init__(self, registry: EventRegistry) -> None:
        self._registry = registry

    def generate_schema(self) -> dict:
        """Generate the full docs schema — called once on page load."""
        events = []
        for definition in self._registry.all():
            events.append({
                "name": definition.name,
                "namespace": definition.namespace,
                "description": definition.description,
                "tags": definition.tags,
                "deprecated": definition.deprecated,
                "ordered": definition.ordered,
                "payload": self._model_schema(definition.payload_model),
                "emits": [
                    {
                        "event": e.event,
                        "description": e.description,
                        "schema": self._model_schema(e.model),
                    }
                    for e in definition.emits
                ],
                "broadcasts": [
                    {
                        "event": b.event,
                        "room": b.room,
                        "description": b.description,
                        "schema": self._model_schema(b.model),
                    }
                    for b in definition.broadcasts
                ],
            })
        return {
            "version": __version__,
            "events": events,
        }

    def _model_schema(self, model: type[BaseModel] | None) -> dict | None:
        if model is None:
            return None
        return model.model_json_schema()
```

---

### 5.19 `docs/ui/` — The Swagger-Style Interface

**`index.html`** — Shell page, loads `main.js` and `style.css`. Includes a top bar with:
- Project name + version
- WebSocket URL display
- Connect / Disconnect toggle button (🔴/🟢)
- Authorize button (opens modal for JWT / API key input)

**`main.js`** — Fetches `/socket-docs/schema` on load. Renders:
- Left sidebar grouped by tags/namespace
- Each event as a collapsible card
- Card shows: direction badge, name, description, payload schema, emits, broadcasts, errors
- "Try it out" → JSON editor pre-filled with example payload → "Send Event" button
- Bottom log drawer (real-time, all WS frames, filterable)

**`style.css`** — Swagger-familiar styling:
- Same color system (blue for primary, green for EMIT, purple for BROADCAST, orange for LISTEN)
- Familiar card layout
- Dark mode support via `prefers-color-scheme`

**Message format the test UI sends:**
```json
{
    "event": "send_message",
    "payload": {
        "room": "lobby",
        "text": "hello"
    }
}
```

**This is also the wire format all real clients use.** The test UI is not special — it is just another client using the standard message format.

---

### 5.20 `__init__.py` — Public API Surface

Everything a user ever needs to import from `socketspec`:

```python
from socketspec.app import SocketApp
from socketspec.connection import Connection, Identity
from socketspec.registry import Emits, Broadcasts, EventDefinition
from socketspec.session import SessionConfig
from socketspec.rooms import Room
from socketspec.di import Depends
from socketspec.errors import (
    SocketSpecError,
    DuplicateEventError,
    ReservedEventNameError,
    RoomPermissionError,
    AuthenticationError,
)
from socketspec.security.auth import JWTAuth, APIKeyAuth, AuthBackend
from socketspec.security.ratelimit import RateLimit
from socketspec.backends.base import BackendAdapter
from socketspec._version import __version__

__all__ = [
    "SocketApp",
    "Connection", "Identity",
    "Emits", "Broadcasts",
    "SessionConfig",
    "Room",
    "Depends",
    "JWTAuth", "APIKeyAuth", "AuthBackend",
    "RateLimit",
    "BackendAdapter",
    "SocketSpecError", "DuplicateEventError",
    "ReservedEventNameError", "RoomPermissionError",
    "AuthenticationError",
    "__version__",
]
```

---

### 5.21 `testing.py` — TestClient

Essential for CI. Ships as part of the package.

```python
class TestClient:
    """
    In-process WebSocket test client. No running server needed.
    Uses anyio memory streams to bypass network entirely.
    """

    def __init__(self, app: SocketApp, *, auth_token: str | None = None) -> None:
        self._app = app
        self._auth_token = auth_token

    @asynccontextmanager
    async def connect(self, *, query_params: dict = {}) -> AsyncIterator[TestConnection]:
        """Context manager that yields a TestConnection."""
        # Creates in-memory stream pair
        # Runs app.handle_connect with fake headers/params
        # Yields TestConnection for emitting/receiving in tests
        ...

class TestConnection:
    async def emit(self, event: EventName, payload: dict) -> None:
        """Send an event to the app as if a client sent it."""
        ...

    async def receive(self, event: EventName, *, timeout: float = 5.0) -> dict:
        """Wait for a specific event to be emitted back."""
        ...

    async def receive_broadcast(self, event: EventName, room: RoomName, *, timeout: float = 5.0) -> dict:
        """Wait for a broadcast event."""
        ...

    async def join_room(self, room: RoomName) -> None:
        """Utility: emit a join event and confirm join."""
        ...
```

---

## 6. Docs UI Specification

### Wire Protocol

Every message — client to server and server to client — uses this envelope:

**Client → Server:**
```json
{
    "event": "event_name",
    "payload": { }
}
```

**Server → Client:**
```json
{
    "event": "event_name",
    "payload": { }
}
```

**Error (Server → Client):**
```json
{
    "event": "__error__",
    "payload": {
        "code": "VALIDATION_ERROR",
        "event": "send_message",
        "message": "Human-readable description",
        "request_id": "uuid",
        "details": { }
    }
}
```

### Docs HTTP Routes (served alongside WS)

```
GET  /socket-docs              → serves index.html
GET  /socket-docs/schema       → returns DocsEngine.generate_schema() as JSON
GET  /socket-docs/openapi.json → AsyncAPI 3.0 spec (contributor milestone)
```

The schema endpoint is the one the UI JavaScript calls. Everything the UI renders comes from this JSON.

---

## 7. Test Plan

### Unit Tests — Every Module

**`test_registry.py`**
- Register an event → appears in registry
- Register duplicate event → raises `DuplicateEventError`
- Register reserved name → raises `ReservedEventNameError`
- Get non-existent event → returns None
- Validate runs without error on clean registry

**`test_manager.py`**
- Connect a connection → appears in all()
- Disconnect → removed from all()
- Send to existing connection → delivered
- Send to non-existent connection → no error raised
- Two connections with same id → raises (collision detection)

**`test_rooms.py`**
- Join room → appears in members()
- Leave room → removed from members()
- Broadcast to room → all members receive
- Broadcast to empty room → no error
- Guard returns False → RoomPermissionError
- One member disconnects mid-broadcast → others still receive

**`test_ratelimit.py`**
- Within limit → allowed
- Exceed limit → blocked
- Wait for refill → allowed again
- Remove connection → bucket cleaned

**`test_middleware.py`**
- Single middleware executes
- Middleware order is correct (FIFO)
- Middleware can abort chain (not calling next)

**`test_di.py`**
- Simple dependency resolved
- Chained dependency resolved in order
- Yield dependency cleanup called after handler

**`test_session.py`**
- Heartbeat ping sent at interval
- No pong → connection marked dead
- idle_timeout → connection closed
- max_duration → connection closed with warning

### Integration Tests

**`test_event_flow.py`**
```python
async def test_full_event_flow():
    app = SocketApp()

    class Payload(BaseModel):
        text: str

    @app.on("echo", emits=[Emits("echoed", model=Payload)])
    async def handle_echo(conn, payload: Payload):
        await conn.emit("echoed", payload)

    async with TestClient(app).connect() as conn:
        await conn.emit("echo", {"text": "hello"})
        response = await conn.receive("echoed")
        assert response["text"] == "hello"

async def test_unknown_event_returns_error():
    app = SocketApp()
    async with TestClient(app).connect() as conn:
        await conn.emit("nonexistent", {})
        error = await conn.receive("__error__")
        assert error["code"] == "UNKNOWN_EVENT"

async def test_validation_error():
    app = SocketApp()

    class Strict(BaseModel):
        required_field: str

    @app.on("strict")
    async def handle(conn, payload: Strict): ...

    async with TestClient(app).connect() as conn:
        await conn.emit("strict", {})  # missing required_field
        error = await conn.receive("__error__")
        assert error["code"] == "VALIDATION_ERROR"
```

**`test_rooms.py` (integration)**
```python
async def test_broadcast_reaches_room_members():
    app = SocketApp()

    @app.on("join")
    async def handle_join(conn, payload):
        await app.rooms.join(conn, "test_room")

    @app.on("shout")
    async def handle_shout(conn, payload):
        await app.rooms.broadcast("test_room", "shouted", payload)

    client = TestClient(app)
    async with client.connect() as sender, client.connect() as receiver:
        await receiver.emit("join", {})
        await sender.emit("join", {})
        await sender.emit("shout", {"message": "hello"})
        broadcast = await receiver.receive("shouted")
        assert broadcast["message"] == "hello"
```

### Coverage Requirement
- Minimum 90% enforced in CI
- 100% on `errors.py`, `registry.py`, `backends/memory.py`

---

## 8. Documentation Site

### Framework: MkDocs Material

This is what FastAPI uses. It is what makes docs feel like FastAPI docs.

**`mkdocs.yml`**
```yaml
site_name: SocketSpec
site_description: FastAPI-style WebSocket framework with built-in docs and testing
site_url: https://socketspec.dev              # or github.io
repo_url: https://github.com/ByteCraftByLaiba/socketspec
repo_name: socketspec
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    - scheme: default
      primary: deep purple
      accent: purple
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: deep purple
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.code.annotate

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]

markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - pymdownx.tabbed
  - admonition
  - attr_list

nav:
  - Home: index.md
  - Quickstart: quickstart.md
  - Tutorial:
    - Your First Event: tutorial/first-event.md
    - Payload Validation: tutorial/payload-validation.md
    - Rooms: tutorial/rooms.md
    - Broadcasting: tutorial/broadcasting.md
    - Authentication: tutorial/auth.md
  - How-to Guides:
    - FastAPI: how-to/fastapi.md
    - Django: how-to/django.md
    - Starlette: how-to/starlette.md
    - Redis Backend: how-to/redis-backend.md
    - Dependency Injection: how-to/dependency-injection.md
    - Testing: how-to/testing.md
    - Deployment: how-to/deployment.md
  - Reference:
    - SocketApp: reference/socketapp.md
    - Connection: reference/connection.md
    - Rooms: reference/rooms.md
    - Session: reference/session.md
    - Security: reference/security.md
    - Backends: reference/backends.md
  - Contributing:
    - Overview: contributing/index.md
    - New Adapter: contributing/new-adapter.md
    - New Backend: contributing/new-backend.md
  - Changelog: changelog.md
  - Roadmap: roadmap.md
```

### Documentation Voice

FastAPI's docs work because they follow one rule: **show the code first, explain second.** Every concept page opens with a working code example. No prose introduction. No theory. Code first.

Example pattern for every doc page:
```markdown
# Rooms

Join a connection to a room and broadcast to all members.

```python
@socket.on("join_room")
async def join(conn: Connection, payload: JoinPayload):
    await socket.rooms.join(conn, payload.room)

@socket.on("send_message")
async def message(conn: Connection, payload: MessagePayload):
    await socket.rooms.broadcast(payload.room, "new_message", payload.model_dump())
```

That's it. The connection is now in the room. Every event sent to that room reaches all members.

## How rooms work
...
```

---

## 9. GitHub Configuration

### `.github/workflows/ci.yml`
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  cla:
    runs-on: ubuntu-latest
    steps:
      - name: CLA Assistant
        uses: contributor-assistant/github-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PERSONAL_ACCESS_TOKEN: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
        with:
          path-to-signatures: 'signatures/cla.json'
          path-to-document: 'https://github.com/ByteCraftByLaiba/socketspec/blob/main/CLA.md'

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Lint
        run: ruff check src/ tests/
      - name: Type check
        run: mypy src/socketspec --strict
      - name: Tests
        run: pytest tests/ --cov=socketspec --cov-fail-under=90 -v
```

### `.github/workflows/publish.yml`
```yaml
name: Publish

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install hatch
      - run: hatch build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

### Issue Templates

**`bug_report.yml`**
```yaml
name: Bug Report
description: File a bug report
labels: ["bug", "triage"]
body:
  - type: textarea
    id: description
    label: What happened?
    validations:
      required: true
  - type: textarea
    id: reproduce
    label: Steps to reproduce
    validations:
      required: true
  - type: dropdown
    id: framework
    label: Framework
    options: [FastAPI, Starlette, Django, Quart, Other]
  - type: dropdown
    id: python
    label: Python version
    options: ["3.10", "3.11", "3.12", "3.13"]
  - type: textarea
    id: expected
    label: Expected behavior
  - type: textarea
    id: actual
    label: Actual behavior
```

**`adapter_request.yml`**
```yaml
name: Adapter Request
description: Request support for a new framework
labels: ["adapter", "good first issue"]
body:
  - type: input
    id: framework
    label: Framework name
    validations:
      required: true
  - type: input
    id: repo
    label: Framework repo/docs URL
  - type: textarea
    id: use_case
    label: Why do you need this adapter?
  - type: checkboxes
    id: contribution
    label: Are you willing to contribute this adapter?
    options:
      - label: "Yes, I want to build this"
      - label: "I need someone else to build it"
```

### `PULL_REQUEST_TEMPLATE.md`
```markdown
## What does this PR do?

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] New adapter
- [ ] New backend
- [ ] Documentation
- [ ] Refactor

## Checklist
- [ ] Tests written and passing
- [ ] Type annotations added
- [ ] Docs updated (if user-facing change)
- [ ] CHANGELOG fragment added (`changes/PR_NUMBER.change.md`)
- [ ] `ruff` and `mypy` pass locally
```

### `CONTRIBUTING.md` Structure

```markdown
# Contributing to SocketSpec

SocketSpec is created and maintained by Laiba Shahab. Contributions are welcome
and will be credited. All contributors must sign the CLA before their first PR
is merged — the CLA bot will prompt you automatically.

## Setup (one command)
pip install -e ".[dev]" && pre-commit install

## Running tests
pytest tests/ -v

## How to add a framework adapter
1. Create `src/socketspec/adapters/yourframework.py`
2. Implement `mount(socket_app, app, *, path="/ws")` function
3. Create `FastAPISocketWrapper` equivalent for your framework
4. Add tests in `tests/adapters/test_yourframework_adapter.py`
5. Add a doc page in `docs/how-to/yourframework.md`
6. Update the adapter table in README.md

## How to add a backend
1. Create `src/socketspec/backends/yourbackend.py`
2. Implement all methods from `BackendAdapter` Protocol
3. Add tests in `tests/unit/backends/test_yourbackend.py`
4. Document in `docs/how-to/yourbackend-backend.md`

## Changelog
Add a file to `changes/` named `PR_NUMBER.change.md` with one line describing your change.

## CLA
You will be asked to sign the Contributor License Agreement before your first PR
is merged. This protects both you and the project. See CLA.md for full terms.

## Good first issues
Look for the `good first issue` label on GitHub Issues.
```

### `SECURITY.md`
```markdown
# Security Policy

SocketSpec is maintained by Laiba Shahab.

## Supported Versions
| Version | Supported |
|---------|-----------|
| 0.x     | ✓         |

## Reporting a Vulnerability
Do NOT open a public GitHub issue for security vulnerabilities.

Email: security@[yourdomain].com

Include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (optional)

You will receive a response within 48 hours.
All valid reports will be credited to the reporter in the release notes.
```

### `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
```

---

## 10. PyPI Publishing

### `pyproject.toml` — Complete

```toml
[build-system]
requires = ["hatchling>=1.26"]
build-backend = "hatchling.build"

[project]
name = "socketspec"
version = "0.1.0"
description = "FastAPI-style WebSocket framework with built-in docs and testing"
readme = "README.md"
license = {text = "Apache-2.0"}
authors = [{ name = "Laiba Shahab", email = "its.laiba.shahab@email.com" }]
keywords = ["websocket", "fastapi", "async", "realtime", "pydantic"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Framework :: AsyncIO",
    "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
    "Typing :: Typed",
]
requires-python = ">=3.10"
dependencies = [
    "websockets>=12.0",
    "pydantic>=2.0",
    "anyio>=4.0",
]

[project.optional-dependencies]
redis = ["redis>=5.0"]
fastapi = ["fastapi>=0.100", "uvicorn>=0.29"]
django = ["django>=4.2"]
all = ["socketspec[redis,fastapi,django]"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "httpx>=0.27",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit>=3.7",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.25",
    "towncrier>=23.0",
    "fastapi>=0.100",
    "uvicorn>=0.29",
]

[project.urls]
Homepage = "https://github.com/ByteCraftByLaiba/socketspec"
Documentation = "https://socketspec.dev"
Repository = "https://github.com/ByteCraftByLaiba/socketspec"
Issues = "https://github.com/ByteCraftByLaiba/socketspec/issues"
Changelog = "https://github.com/ByteCraftByLaiba/socketspec/blob/main/CHANGELOG.md"

[tool.hatch.build.targets.wheel]
packages = ["src/socketspec"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--strict-markers"

[tool.mypy]
strict = true
python_version = "3.10"
files = ["src/socketspec"]

[tool.ruff]
target-version = "py310"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "ANN"]

[tool.coverage.run]
source = ["socketspec"]
omit = ["tests/*"]

[tool.towncrier]
package = "socketspec"
package_dir = "src"
filename = "CHANGELOG.md"
directory = "changes"
```

---

## 11. Launch Checklist

### Before v0.1.0 Release

**Code:**
- [ ] All Phase 1 modules implemented
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Coverage ≥ 90%
- [ ] `mypy --strict` passes with zero errors
- [ ] `ruff` passes with zero errors
- [ ] FastAPI adapter working end-to-end
- [ ] Docs UI renders and test panel works
- [ ] TestClient works for automated tests

**Docs:**
- [ ] README with install + 20-line example + badges
- [ ] Quickstart page complete
- [ ] Tutorial: first-event, payload-validation, rooms, auth
- [ ] FastAPI how-to guide
- [ ] API reference for SocketApp and Connection
- [ ] CONTRIBUTING.md complete
- [ ] CHANGELOG.md initialized
- [ ] ROADMAP.md published

**GitHub:**
- [ ] All issue templates added
- [ ] PR template added
- [ ] CI workflow passing on main
- [ ] Labels created: `good first issue`, `adapter: *`, `backend: *`, `docs`, `security`
- [ ] GitHub Discussions enabled
- [ ] PyPI token added as GitHub secret

**PyPI:**
- [ ] Name `socketspec` confirmed available (`pip index versions socketspec`)
- [ ] `hatch build` produces clean wheel and sdist
- [ ] Test publish to TestPyPI first
- [ ] `pip install socketspec` installs cleanly
- [ ] `pip install socketspec[fastapi]` installs and works
- [ ] Package metadata shows "Laiba Shahab" as author
- [ ] License shows "Apache-2.0"

**IP:**
- [ ] Copyright header in every `.py` file in `src/socketspec/`
- [ ] `AUTHORS` file present at repo root
- [ ] `NOTICE` file present at repo root
- [ ] `CLA.md` file present at repo root
- [ ] CLA Assistant configured and tested on a dummy PR
- [ ] Apache 2.0 `LICENSE` file present at repo root

### Announcement — Same Day as v0.1.0 Tag

**Hacker News (highest priority for dev tools):**
```
Show HN: SocketSpec – FastAPI-style WebSocket framework with built-in Swagger-like UI

Built by Laiba Shahab. Like FastAPI did for HTTP, SocketSpec brings
decorator-based routing, Pydantic validation, and a live interactive
docs UI to WebSockets.

pip install socketspec[fastapi]

- @socket.on() decorators just like FastAPI routes
- Pydantic validation on every event payload
- /socket-docs UI — fire events in browser, no frontend needed
- One-line mounting into FastAPI, Django, Starlette
- Rooms and broadcasting built in
- FastAPI Depends() DI support

GitHub: https://github.com/ByteCraftByLaiba/socketspec
```

**LinkedIn post:** Show the before/after. Old way (throwaway HTML file, rebuilt every change). New way (open /socket-docs, fire event, done). Short. Visual. Credit the project clearly.

**Reddit r/Python and r/FastAPI:** Link to GitHub + HN post. Do not cross-post the same text.

---

*This document is the complete implementation specification for SocketSpec by Laiba Shahab. Build in the order listed in Section 4. Every module has its contract specified. Every test is outlined. Every config file is complete. Cursor implements this from top to bottom.*
