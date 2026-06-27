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

"""Origin header validation during the HTTP WebSocket upgrade handshake.

Owns allowed-origin checks only. Does NOT own authentication or routing.
"""

from __future__ import annotations

WILDCARD_ORIGIN = "*"


class OriginValidator:
    """Validates the Origin header on WebSocket upgrade requests."""

    def __init__(self, allowed_origins: list[str]) -> None:
        self._allowed = set(allowed_origins)
        self._allow_all = WILDCARD_ORIGIN in allowed_origins

    def is_allowed(self, origin: str | None) -> bool:
        """Return whether the given Origin header value is permitted.

        Args:
            origin: Value of the HTTP Origin header, if present.

        Returns:
            True if the origin is allowed, False otherwise.
        """
        if self._allow_all:
            return True
        if origin is None:
            return False
        return origin in self._allowed
