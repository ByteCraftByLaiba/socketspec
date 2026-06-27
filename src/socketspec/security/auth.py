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

"""Authentication protocol and built-in auth backend implementations.

Owns connect-time authentication only. Does NOT own session management
or token refresh handling beyond returning token expiry metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from socketspec.connection import Identity

logger = logging.getLogger(__name__)

DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_HEADER = "authorization"
DEFAULT_API_KEY_HEADER = "x-api-key"
BEARER_PREFIX = "bearer "
QUERY_TOKEN_PARAM = "token"
QUERY_API_KEY_PARAM = "api_key"


@runtime_checkable
class AuthBackend(Protocol):
    """Protocol for WebSocket connection authentication backends."""

    async def authenticate(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Identity | None:
        """Authenticate a connection from upgrade headers and query params.

        Args:
            headers: HTTP headers from the WebSocket upgrade request.
            query_params: Query string parameters from the upgrade URL.

        Returns:
            An Identity if authentication succeeds, otherwise None.
        """


class JWTAuth:
    """Validate JSON Web Tokens from a header or query parameter."""

    def __init__(
        self,
        secret: str,
        algorithm: str = DEFAULT_JWT_ALGORITHM,
        header: str = DEFAULT_JWT_HEADER,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._header = header.lower()

    async def authenticate(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Identity | None:
        """Decode a JWT and return the resulting identity."""
        token = self._extract_token(headers, query_params)
        if token is None:
            return None
        try:
            import jwt
        except ImportError:
            logger.error("PyJWT is required for JWTAuth but is not installed")
            return None

        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
            )
        except jwt.PyJWTError:
            logger.debug("JWT authentication failed")
            return None

        user_id = payload.get("sub")
        if user_id is not None and not isinstance(user_id, str):
            user_id = str(user_id)

        scopes_raw = payload.get("scopes", [])
        scopes = (
            [str(scope) for scope in scopes_raw]
            if isinstance(scopes_raw, list)
            else []
        )

        token_expires_at: datetime | None = None
        exp = payload.get("exp")
        if isinstance(exp, (int, float)):
            token_expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

        claims = {key: value for key, value in payload.items() if key != "scopes"}

        return Identity(
            user_id=user_id,
            scopes=scopes,
            claims=claims,
            raw_token=token,
            token_expires_at=token_expires_at,
        )

    def _extract_token(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> str | None:
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        header_value = normalized_headers.get(self._header)
        if header_value:
            if header_value.lower().startswith(BEARER_PREFIX):
                return header_value[len(BEARER_PREFIX) :].strip()
            return header_value.strip()
        return query_params.get(QUERY_TOKEN_PARAM)


class APIKeyAuth:
    """Validate a static API key from a header or query parameter."""

    def __init__(
        self,
        api_key: str,
        header: str = DEFAULT_API_KEY_HEADER,
    ) -> None:
        self._api_key = api_key
        self._header = header.lower()

    async def authenticate(
        self,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> Identity | None:
        """Return an identity when the provided API key matches."""
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        key = normalized_headers.get(self._header) or query_params.get(
            QUERY_API_KEY_PARAM
        )
        if key == self._api_key:
            return Identity()
        return None
