# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import pytest

from socketspec.errors import DuplicateEventError, ReservedEventNameError
from socketspec.registry import EventDefinition, EventRegistry


async def _noop_handler(conn: object, payload: object) -> None:
    pass


def _definition(name: str) -> EventDefinition:
    return EventDefinition(
        name=name,
        namespace="/",
        handler=_noop_handler,
        payload_model=None,
        emits=[],
        broadcasts=[],
        description="",
        tags=[],
        ordered=False,
        executor=False,
    )


def test_register_event_appears_in_registry() -> None:
    registry = EventRegistry()
    registry.register(_definition("ping"))
    assert registry.get("/", "ping") is not None


def test_register_duplicate_event_raises_duplicate_error() -> None:
    registry = EventRegistry()
    registry.register(_definition("dup"))
    with pytest.raises(DuplicateEventError):
        registry.register(_definition("dup"))


def test_register_reserved_name_raises_reserved_error() -> None:
    registry = EventRegistry()
    with pytest.raises(ReservedEventNameError):
        registry.register(_definition("__error__"))


def test_get_missing_event_returns_none() -> None:
    registry = EventRegistry()
    assert registry.get("/", "missing") is None


def test_validate_runs_without_error_on_clean_registry() -> None:
    registry = EventRegistry()
    registry.register(_definition("ok"))
    registry.validate()
