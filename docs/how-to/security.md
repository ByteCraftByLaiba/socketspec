# Authentication and Security

SocketSpec provides a layered security model: origin validation at the transport level, authentication at connection time, rate limiting per connection, and room-level access control. This guide covers configuration and best practices for each layer.

---

## Origin Validation

Origin validation restricts which domains can establish WebSocket connections. It runs before authentication and before the connection is registered.

```python
socket = SocketApp(
    allowed_origins=["https://myapp.com", "https://staging.myapp.com"],
)
```

Connections from unlisted origins are immediately closed with code `4003`. The default value `["*"]` permits all origins, which is appropriate only for development.

!!! warning "Production Deployments"
    Always specify explicit origins in production. WebSocket connections bypass standard CORS protections, making origin validation your primary defense against cross-site WebSocket hijacking.

---

## Authentication Backends

Authentication runs immediately after origin validation. If the backend returns `None`, SocketSpec sends an `AUTH_ERROR` event and closes the connection with code `4001`.

### JWT Authentication

```python
from socketspec.security.auth import JWTAuth

socket = SocketApp(
    auth=JWTAuth(secret="your-256-bit-secret", algorithm="HS256"),
)
```

The JWT is read from one of two locations (checked in order):

1. `Authorization: Bearer <token>` header
2. `?token=<token>` query parameter

On success, `conn.identity` is populated with claims from the token:

| Identity Field | JWT Claim |
|---|---|
| `user_id` | `sub` |
| `role` | `role` |
| `scopes` | `scopes` |
| `token_expires_at` | `exp` |

SocketSpec monitors token expiry during the session. When the token is within the configured `token_refresh_window` of expiring, the client receives an `__auth_expiring__` event.

### API Key Authentication

```python
from socketspec.security.auth import APIKeyAuth

socket = SocketApp(
    auth=APIKeyAuth(api_key="your-api-key"),
)
```

The API key is read from the same locations as JWT tokens. Key comparison uses constant-time comparison (`hmac.compare_digest`) to prevent timing attacks.

For multiple valid keys:

```python
auth=APIKeyAuth(valid_keys={"key-alpha", "key-beta", "key-gamma"})
```

### Custom Authentication Backend

Implement the `AuthBackend` protocol for any authentication scheme:

```python
from socketspec.security.auth import AuthBackend, Identity

class CustomAuth(AuthBackend):
    async def authenticate(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Identity | None:
        token = headers.get("x-custom-token")
        if token is None:
            return None

        user = await verify_token(token)  # your verification logic
        if user is None:
            return None

        return Identity(user_id=user.id, role=user.role)
```

---

## Rate Limiting

Rate limiting uses a token bucket algorithm applied per connection. Each connection starts with a full bucket and tokens are replenished at a fixed rate.

```python
from socketspec.security.ratelimit import RateLimit

socket = SocketApp(
    rate_limit=RateLimit(rate=10, capacity=20),
)
```

| Parameter | Type | Description |
|---|---|---|
| `rate` | `float` | Tokens replenished per second |
| `capacity` | `int` | Maximum bucket size (burst capacity) |

When the bucket is empty, the client receives a `RATE_LIMIT_ERROR` event. The connection is not closed -- the client can retry after tokens replenish.

---

## Session Configuration

Session management controls connection lifecycle: heartbeat probes detect ghost connections, idle timeouts free abandoned connections, and max duration enforces absolute session limits.

```python
from socketspec.session import SessionConfig

socket = SocketApp(
    session=SessionConfig(
        heartbeat_interval=25,    # seconds between ping probes
        heartbeat_timeout=10,     # seconds to wait for pong response
        idle_timeout=300,         # disconnect after 5 minutes of inactivity
        max_duration=3600,        # absolute session limit: 1 hour
        token_refresh_window=60,  # warn 60 seconds before JWT expires
    ),
)
```

All timeouts are optional. Set a value to `0` to disable it.

---

## Securing the Documentation UI

The `/socket-docs` UI can be protected with an access token:

```python
socket = SocketApp(
    docs=True,
    docs_access_token="your-docs-secret",
)
```

Access is granted via:

- `?token=your-docs-secret` query parameter
- `Authorization: Bearer your-docs-secret` header

Token comparison uses constant-time comparison to prevent timing attacks.

---

## Security Checklist

Before deploying to production:

- [ ] Set `allowed_origins` to your application domains (remove `["*"]`)
- [ ] Configure an `AuthBackend` (JWT or API key)
- [ ] Set `rate_limit` to prevent abuse
- [ ] Set `max_payload_size` to a reasonable value for your use case
- [ ] Set `docs_access_token` or disable docs entirely (`docs=False`)
- [ ] Use TLS termination (wss://) in front of your application server
