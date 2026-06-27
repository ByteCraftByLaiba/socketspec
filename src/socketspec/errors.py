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

"""Custom exception classes and system constants for SocketSpec.

Owns all exception types and reserved name/error code constants.
Does NOT own any runtime logic or error formatting.
"""

from __future__ import annotations

RESERVED_EVENTS: frozenset[str] = frozenset({
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

ERROR_CODES: frozenset[str] = frozenset({
    "AUTH_ERROR",
    "AUTH_EXPIRED",
    "HANDLER_ERROR",
    "IDLE_TIMEOUT",
    "PAYLOAD_TOO_LARGE",
    "PERMISSION_ERROR",
    "RATE_LIMIT_ERROR",
    "ROOM_NOT_FOUND",
    "SESSION_EXPIRED",
    "UNKNOWN_EVENT",
    "VALIDATION_ERROR",
})


class SocketSpecError(Exception):
    """Base exception for all SocketSpec errors."""


class DuplicateEventError(SocketSpecError):
    """Raised at startup when two handlers register the same event name."""


class ReservedEventNameError(SocketSpecError):
    """Raised when a user tries to register a reserved system event name."""


class ConnectionNotFoundError(SocketSpecError):
    """Raised when an operation targets a connection_id that does not exist."""


class DuplicateConnectionError(SocketSpecError):
    """Raised when a connection with the same id is registered twice."""


class RoomNotFoundError(SocketSpecError):
    """Raised when broadcasting to a room that does not exist."""


class AuthenticationError(SocketSpecError):
    """Raised when authentication fails during connect."""


class PayloadTooLargeError(SocketSpecError):
    """Raised when an incoming payload exceeds max_payload_size."""


class RoomPermissionError(SocketSpecError):
    """Raised when a room guard returns False."""


class StartupValidationError(SocketSpecError):
    """Raised during startup validation before the server accepts connections."""
