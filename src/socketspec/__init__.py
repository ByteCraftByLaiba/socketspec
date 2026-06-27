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

"""SocketSpec public API."""

from __future__ import annotations

from socketspec._version import __version__
from socketspec.app import SocketApp
from socketspec.backends.base import BackendAdapter
from socketspec.connection import Connection, Identity
from socketspec.di import Depends
from socketspec.errors import (
    AuthenticationError,
    DuplicateEventError,
    ReservedEventNameError,
    RoomPermissionError,
    SocketSpecError,
)
from socketspec.registry import Broadcasts, Emits, EventDefinition
from socketspec.rooms import Room
from socketspec.security.auth import APIKeyAuth, AuthBackend, JWTAuth
from socketspec.security.ratelimit import RateLimit
from socketspec.session import SessionConfig
from socketspec.testing import TestClient, TestConnection

__all__ = [
    "APIKeyAuth",
    "AuthBackend",
    "BackendAdapter",
    "Broadcasts",
    "Connection",
    "Depends",
    "DuplicateEventError",
    "Emits",
    "EventDefinition",
    "Identity",
    "JWTAuth",
    "RateLimit",
    "ReservedEventNameError",
    "Room",
    "RoomPermissionError",
    "AuthenticationError",
    "SessionConfig",
    "SocketApp",
    "SocketSpecError",
    "TestClient",
    "TestConnection",
    "__version__",
]
