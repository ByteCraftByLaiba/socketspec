# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for socketspec.errors — exceptions and system constants."""

from __future__ import annotations

import pytest

from socketspec.errors import (
    ERROR_CODES,
    RESERVED_EVENTS,
    AuthenticationError,
    ConnectionNotFoundError,
    DuplicateConnectionError,
    DuplicateEventError,
    PayloadTooLargeError,
    ReservedEventNameError,
    RoomNotFoundError,
    RoomPermissionError,
    SocketSpecError,
    StartupValidationError,
)

ALL_EXCEPTION_CLASSES = [
    SocketSpecError,
    DuplicateEventError,
    ReservedEventNameError,
    ConnectionNotFoundError,
    DuplicateConnectionError,
    RoomNotFoundError,
    AuthenticationError,
    PayloadTooLargeError,
    RoomPermissionError,
    StartupValidationError,
]


def test_socketspec_error_is_base_exception() -> None:
    assert issubclass(SocketSpecError, Exception)


def test_all_exception_classes_are_instantiable() -> None:
    for cls in ALL_EXCEPTION_CLASSES:
        exc = cls("test message")
        assert str(exc) == "test message"


def test_all_exceptions_inherit_from_socketspec_error() -> None:
    subclasses = ALL_EXCEPTION_CLASSES[1:]  # everything except the base
    for cls in subclasses:
        assert issubclass(cls, SocketSpecError), (
            f"{cls.__name__} must inherit SocketSpecError"
        )


def test_all_exceptions_can_be_raised_and_caught() -> None:
    for cls in ALL_EXCEPTION_CLASSES:
        with pytest.raises(SocketSpecError):
            raise cls("raised")


def test_duplicate_event_error_carries_message() -> None:
    exc = DuplicateEventError("event 'join' already registered")
    assert "join" in str(exc)


def test_reserved_events_frozenset_contains_all_system_events() -> None:
    assert isinstance(RESERVED_EVENTS, frozenset)
    assert len(RESERVED_EVENTS) >= 9


def test_reserved_events_includes_ping_pong() -> None:
    assert "__ping__" in RESERVED_EVENTS
    assert "__pong__" in RESERVED_EVENTS


def test_reserved_events_includes_error_and_connect() -> None:
    assert "__error__" in RESERVED_EVENTS
    assert "__connect__" in RESERVED_EVENTS
    assert "__disconnect__" in RESERVED_EVENTS


def test_reserved_events_includes_auth_expiring() -> None:
    assert "__auth_expiring__" in RESERVED_EVENTS


def test_reserved_events_includes_session_expiring() -> None:
    assert "__session_expiring__" in RESERVED_EVENTS


def test_reserved_events_includes_idle_warning() -> None:
    assert "__idle_warning__" in RESERVED_EVENTS


def test_error_codes_frozenset_contains_all_known_codes() -> None:
    assert isinstance(ERROR_CODES, frozenset)
    assert len(ERROR_CODES) >= 10


def test_error_codes_includes_auth_error() -> None:
    assert "AUTH_ERROR" in ERROR_CODES


def test_error_codes_includes_auth_expired() -> None:
    assert "AUTH_EXPIRED" in ERROR_CODES


def test_error_codes_includes_handler_error() -> None:
    assert "HANDLER_ERROR" in ERROR_CODES


def test_error_codes_includes_idle_timeout() -> None:
    assert "IDLE_TIMEOUT" in ERROR_CODES


def test_error_codes_includes_payload_too_large() -> None:
    assert "PAYLOAD_TOO_LARGE" in ERROR_CODES


def test_error_codes_includes_permission_error() -> None:
    assert "PERMISSION_ERROR" in ERROR_CODES


def test_error_codes_includes_rate_limit_error() -> None:
    assert "RATE_LIMIT_ERROR" in ERROR_CODES


def test_error_codes_includes_room_not_found() -> None:
    assert "ROOM_NOT_FOUND" in ERROR_CODES


def test_error_codes_includes_session_expired() -> None:
    assert "SESSION_EXPIRED" in ERROR_CODES


def test_error_codes_includes_unknown_event() -> None:
    assert "UNKNOWN_EVENT" in ERROR_CODES


def test_error_codes_includes_validation_error() -> None:
    assert "VALIDATION_ERROR" in ERROR_CODES


def test_reserved_events_is_immutable() -> None:
    with pytest.raises((AttributeError, TypeError)):
        RESERVED_EVENTS.add("__custom__")  # type: ignore[attr-defined]


def test_error_codes_is_immutable() -> None:
    with pytest.raises((AttributeError, TypeError)):
        ERROR_CODES.add("CUSTOM_CODE")  # type: ignore[attr-defined]
