# Security API Reference

## Authentication Backends

### JWTAuth

::: socketspec.security.auth.JWTAuth

JSON Web Token authentication backend.

```python
from socketspec.security.auth import JWTAuth

auth = JWTAuth(secret="your-256-bit-secret", algorithm="HS256")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `secret` | `str` | -- | The signing secret or public key |
| `algorithm` | `str` | `"HS256"` | JWT signing algorithm |

**Token lookup order:**

1. `Authorization: Bearer <token>` header
2. `?token=<token>` query parameter

**Identity mapping:**

| `Identity` field | JWT claim |
|---|---|
| `user_id` | `sub` |
| `role` | `role` |
| `scopes` | `scopes` |
| `token_expires_at` | `exp` |

---

### APIKeyAuth

::: socketspec.security.auth.APIKeyAuth

API key authentication backend. Key comparison uses `hmac.compare_digest` for constant-time comparison.

```python
from socketspec.security.auth import APIKeyAuth

# Single key
auth = APIKeyAuth(api_key="your-api-key")

# Multiple keys
auth = APIKeyAuth(valid_keys={"key-alpha", "key-beta"})
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str \| None` | `None` | Single valid API key |
| `valid_keys` | `set[str] \| None` | `None` | Set of valid API keys (use instead of `api_key` for multiple keys) |

---

### AuthBackend Protocol

Implement this protocol to create custom authentication backends:

```python
from socketspec.security.auth import AuthBackend, Identity

class CustomAuth(AuthBackend):
    async def authenticate(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Identity | None:
        """Return an Identity on success, or None to reject the connection."""
        ...
```

---

### Identity

::: socketspec.security.auth.Identity

Represents the authenticated identity of a connection.

```python
@dataclass
class Identity:
    user_id: str | None = None
    role: str | None = None
    scopes: list[str] = field(default_factory=list)
    token_expires_at: datetime | None = None
    extra: dict = field(default_factory=dict)
```

For unauthenticated connections (no `auth=` configured), all fields retain their default values.

---

## Rate Limiting

### RateLimit

::: socketspec.security.ratelimit.RateLimit

Token bucket rate limiter applied per connection.

```python
from socketspec.security.ratelimit import RateLimit

rate_limit = RateLimit(rate=10, capacity=20)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rate` | `float` | -- | Tokens replenished per second |
| `capacity` | `int` | -- | Maximum bucket size (burst capacity) |

When the bucket is empty, the client receives a `RATE_LIMIT_ERROR` envelope. The connection remains open.

---

## Origin Validation

### OriginValidator

Origin validation is configured through `SocketApp` constructor parameters:

```python
socket = SocketApp(
    allowed_origins=["https://myapp.com", "https://staging.myapp.com"],
)
```

| Value | Behavior |
|---|---|
| `["*"]` (default) | All origins are permitted |
| `["https://myapp.com"]` | Only exact matches are permitted |
| `[]` | All origins are rejected |

Origins are compared using exact string matching. Note that `https://myapp.com` and `https://myapp.com:443` are treated as different origins. Trailing slashes are significant.

Rejected connections are closed with WebSocket close code `4003`.

---

## Session Configuration

### SessionConfig

::: socketspec.session.SessionConfig

Controls connection lifecycle timers.

```python
from socketspec.session import SessionConfig

config = SessionConfig(
    heartbeat_interval=25,
    heartbeat_timeout=10,
    idle_timeout=300,
    max_duration=3600,
    token_refresh_window=60,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `heartbeat_interval` | `int` | `25` | Seconds between `__ping__` probes |
| `heartbeat_timeout` | `int` | `10` | Seconds to wait for `__pong__` before closing |
| `idle_timeout` | `int` | `0` | Disconnect after this many seconds of inactivity (0 = disabled) |
| `max_duration` | `int` | `0` | Absolute session length limit in seconds (0 = disabled) |
| `token_refresh_window` | `int` | `60` | Send `__auth_expiring__` this many seconds before JWT expires |
