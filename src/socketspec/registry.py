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

"""Event registry storing all registered socket event definitions.

Owns registration, lookup, and startup validation of events.
Does NOT own routing, dispatch, or handler execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from socketspec.errors import (
    RESERVED_EVENTS,
    DuplicateEventError,
    ReservedEventNameError,
)
from socketspec.types import EventName, HandlerFunc, Namespace


@dataclass
class Emits:
    """Metadata describing an event a handler may emit back to the sender."""

    event: EventName
    model: type[BaseModel] | None = None
    description: str = ""


@dataclass
class Broadcasts:
    """Metadata describing an event a handler may broadcast to a room."""

    event: EventName
    room: str
    model: type[BaseModel] | None = None
    description: str = ""


@dataclass
class EventDefinition:
    """One registered socket event and its handler metadata."""

    name: EventName
    namespace: Namespace
    handler: HandlerFunc
    payload_model: type[BaseModel] | None
    emits: list[Emits]
    broadcasts: list[Broadcasts]
    description: str
    tags: list[str]
    ordered: bool
    executor: bool
    deprecated: bool = False
    dependencies: list[Any] = field(default_factory=list)


class EventRegistry:
    """Single source of truth for all socket events in the application.

    Note:
        Read-write at registration time, read-only at runtime after validation.
    """

    def __init__(self) -> None:
        self._events: dict[tuple[Namespace, EventName], EventDefinition] = {}
        self._validated: bool = False

    def register(self, definition: EventDefinition) -> None:
        """Register an event definition.

        Args:
            definition: Complete event metadata and handler reference.

        Raises:
            ReservedEventNameError: If the event name is reserved for system use.
            DuplicateEventError: If the event is already registered in the namespace.
        """
        if definition.name in RESERVED_EVENTS:
            raise ReservedEventNameError(
                f"'{definition.name}' is a reserved event name."
            )
        key = (definition.namespace, definition.name)
        if key in self._events:
            raise DuplicateEventError(
                f"Event '{definition.name}' already registered in namespace "
                f"'{definition.namespace}'."
            )
        self._events[key] = definition

    def get(self, namespace: Namespace, name: EventName) -> EventDefinition | None:
        """Look up an event definition by namespace and name."""
        return self._events.get((namespace, name))

    def all(self) -> list[EventDefinition]:
        """Return all registered event definitions."""
        return list(self._events.values())

    def validate(self) -> None:
        """Run startup validations before the server accepts connections.

        Raises:
            StartupValidationError: If cross-event validation fails.
        """
        self._validated = True
