# Dependency Injection

SocketSpec supports FastAPI-style dependency injection using `Depends()`. Dependencies are resolved per event invocation and support generator-based cleanup through `AsyncExitStack`.

---

## Basic Usage

Declare dependencies as default parameter values in your handler signature:

```python
from socketspec import SocketApp, Connection
from socketspec.di import Depends

socket = SocketApp()

def get_db():
    return DatabaseConnection()

@socket.on("fetch_user")
async def fetch_user(
    conn: Connection,
    payload: dict,
    db = Depends(get_db),
) -> None:
    user = await db.query("SELECT * FROM users WHERE id = ?", conn.identity.user_id)
    await conn.emit("user_data", user)
```

The `get_db` function is called each time the handler is invoked. The return value is injected as the `db` parameter.

---

## Async Dependencies

Dependencies can be synchronous or asynchronous:

```python
async def get_user_profile(conn: Connection):
    return await fetch_profile(conn.identity.user_id)

@socket.on("dashboard")
async def dashboard(
    conn: Connection,
    payload: dict,
    profile = Depends(get_user_profile),
) -> None:
    await conn.emit("dashboard_data", {"name": profile.name})
```

---

## Generator Dependencies (Cleanup)

Use `yield` to run cleanup logic after the handler completes, regardless of whether it raised an exception:

```python
async def get_db_session():
    session = await create_session()
    try:
        yield session
    finally:
        await session.close()

@socket.on("save_data")
async def save_data(
    conn: Connection,
    payload: dict,
    session = Depends(get_db_session),
) -> None:
    await session.execute(...)
    # session.close() runs automatically after this handler returns
```

This pattern is identical to FastAPI's `yield` dependencies. Cleanup runs through `AsyncExitStack`, ensuring resources are released even if the handler raises.

---

## Nested Dependencies

Dependencies can depend on other dependencies:

```python
def get_config():
    return AppConfig(database_url="postgres://...")

async def get_db(config = Depends(get_config)):
    return await connect(config.database_url)

@socket.on("query")
async def query_handler(
    conn: Connection,
    payload: dict,
    db = Depends(get_db),
) -> None:
    result = await db.execute(payload["sql"])
    await conn.emit("result", result)
```

The dependency tree is resolved depth-first. `get_config` runs first, its result is passed to `get_db`, and the final `db` value is injected into the handler.

!!! note "No Deduplication"
    SocketSpec does not cache or deduplicate dependency calls. If the same dependency appears in multiple branches of the dependency tree, it will be called once per branch. This is intentional -- caching semantics are left to the application.

---

## Accessing Connection in Dependencies

Dependencies can receive the `Connection` object by declaring it as a parameter:

```python
async def require_admin(conn: Connection):
    if conn.identity.role != "admin":
        raise PermissionError("Admin access required")
    return conn.identity

@socket.on("admin_action")
async def admin_action(
    conn: Connection,
    payload: dict,
    admin = Depends(require_admin),
) -> None:
    # admin is the verified Identity object
    await conn.emit("admin_result", {"user": admin.user_id})
```

If the dependency raises an exception, the handler is not called and the client receives a `HANDLER_ERROR` envelope.

---

## Testing with Dependencies

Dependencies work transparently in `TestClient`. For testing, you can override dependencies by constructing your `SocketApp` with test-specific factories, or by using standard Python mocking.
