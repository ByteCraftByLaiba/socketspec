# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from socketspec.errors import (
    ERROR_CODES,
    RESERVED_EVENTS,
    DuplicateEventError,
    ReservedEventNameError,
    SocketSpecError,
)


def test_reserved_events_contains_system_events() -> None:
    assert "__error__" in RESERVED_EVENTS
    assert "__ping__" in RESERVED_EVENTS


def test_error_codes_contains_validation_error() -> None:
    assert "VALIDATION_ERROR" in ERROR_CODES


def test_socket_spec_error_is_base_exception() -> None:
    assert issubclass(DuplicateEventError, SocketSpecError)
    assert issubclass(ReservedEventNameError, SocketSpecError)
