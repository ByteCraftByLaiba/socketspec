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

"""Shared type aliases used across SocketSpec modules.

Owns type aliases only. Does NOT own logic or imports from other socketspec modules.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

EventName = str
ConnectionId = str
RoomName = str
Namespace = str
HandlerFunc = Callable[..., Awaitable[None]]
PayloadDict = dict[str, Any]
ErrorCode = str
