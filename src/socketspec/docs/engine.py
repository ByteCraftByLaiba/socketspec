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

"""Reads the event registry and produces JSON schema for the docs UI.

Owns schema generation from registered events. Does NOT serve HTTP routes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from socketspec._version import __version__
from socketspec.registry import EventRegistry


class DocsEngine:
    """Generates documentation schema from the event registry."""

    def __init__(self, registry: EventRegistry) -> None:
        self._registry = registry

    def generate_schema(self) -> dict[str, Any]:
        """Build the full docs schema for the interactive UI.

        Returns:
            JSON-serializable schema with version and event definitions.
        """
        events: list[dict[str, Any]] = []
        for definition in self._registry.all():
            events.append(
                {
                    "name": definition.name,
                    "namespace": definition.namespace,
                    "description": definition.description,
                    "tags": definition.tags,
                    "deprecated": definition.deprecated,
                    "ordered": definition.ordered,
                    "payload": self._model_schema(definition.payload_model),
                    "emits": [
                        {
                            "event": emit.event,
                            "description": emit.description,
                            "schema": self._model_schema(emit.model),
                        }
                        for emit in definition.emits
                    ],
                    "broadcasts": [
                        {
                            "event": broadcast.event,
                            "room": broadcast.room,
                            "description": broadcast.description,
                            "schema": self._model_schema(broadcast.model),
                        }
                        for broadcast in definition.broadcasts
                    ],
                }
            )
        return {
            "version": __version__,
            "events": events,
        }

    def _model_schema(self, model: type[BaseModel] | None) -> dict[str, Any] | None:
        if model is None:
            return None
        return model.model_json_schema()
