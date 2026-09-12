# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for socketspec.registry — EventRegistry registration, lookup, validation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pydantic import BaseModel

from socketspec.connection import Connection
from socketspec.errors import DuplicateEventError, ReservedEventNameError
from socketspec.registry import Broadcasts, Emits, EventDefinition, EventRegistry

# ── Helpers ──────────────────────────────────────────────────────────────────


def _bare_handler() -> Callable[[Connection, dict[str, Any]], Awaitable[None]]:
    async def handler(conn: Connection, payload: dict[str, Any]) -> None:
        pass

    return handler


def _make_def(
    name: str = "test_event",
    namespace: str = "/",
    payload_model: type[BaseModel] | None = None,
    emits: list[Emits] | None = None,
    broadcasts: list[Broadcasts] | None = None,
    description: str = "",
    tags: list[str] | None = None,
    ordered: bool = False,
    executor: bool = False,
    deprecated: bool = False,
) -> EventDefinition:
    return EventDefinition(
        name=name,
        namespace=namespace,
        handler=_bare_handler(),
        payload_model=payload_model,
        emits=emits or [],
        broadcasts=broadcasts or [],
        description=description,
        tags=tags or [],
        ordered=ordered,
        executor=executor,
        deprecated=deprecated,
    )


# ── Registration ──────────────────────────────────────────────────────────────


def test_register_event_stores_in_registry() -> None:
    reg = EventRegistry()
    reg.register(_make_def("chat"))
    assert reg.get("/", "chat") is not None


def test_register_event_is_retrievable_by_namespace_and_name() -> None:
    reg = EventRegistry()
    defn = _make_def("join", namespace="/chat")
    reg.register(defn)
    assert reg.get("/chat", "join") is defn


def test_register_duplicate_event_raises_duplicate_error() -> None:
    reg = EventRegistry()
    reg.register(_make_def("chat"))
    with pytest.raises(DuplicateEventError):
        reg.register(_make_def("chat"))


def test_register_duplicate_event_same_name_different_namespace_succeeds() -> None:
    reg = EventRegistry()
    reg.register(_make_def("join", namespace="/"))
    reg.register(_make_def("join", namespace="/admin"))  # must not raise
    assert reg.get("/", "join") is not None
    assert reg.get("/admin", "join") is not None


# ── Reserved names ────────────────────────────────────────────────────────────


def test_register_reserved_name_error_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__error__"))


def test_register_reserved_name_connect_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__connect__"))


def test_register_reserved_name_disconnect_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__disconnect__"))


def test_register_reserved_name_ping_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__ping__"))


def test_register_reserved_name_pong_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__pong__"))


def test_register_reserved_name_auth_expiring_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__auth_expiring__"))


def test_register_reserved_name_session_expiring_raises() -> None:
    with pytest.raises(ReservedEventNameError):
        EventRegistry().register(_make_def("__session_expiring__"))


# ── Lookup ────────────────────────────────────────────────────────────────────


def test_get_nonexistent_event_returns_none() -> None:
    assert EventRegistry().get("/", "no_such_event") is None


def test_get_wrong_namespace_returns_none() -> None:
    reg = EventRegistry()
    reg.register(_make_def("ping", namespace="/"))
    assert reg.get("/other", "ping") is None


def test_all_returns_all_registered_events() -> None:
    reg = EventRegistry()
    reg.register(_make_def("a"))
    reg.register(_make_def("b"))
    assert len(reg.all()) == 2


def test_all_returns_empty_list_when_no_events_registered() -> None:
    assert EventRegistry().all() == []


# ── Validate ──────────────────────────────────────────────────────────────────


def test_validate_succeeds_on_clean_registry() -> None:
    reg = EventRegistry()
    reg.validate()  # must not raise


# ── Metadata ──────────────────────────────────────────────────────────────────


def test_emits_metadata_stored_on_definition() -> None:
    class Reply(BaseModel):
        ok: bool

    emits = [Emits(event="reply", model=Reply, description="A reply")]
    defn = _make_def(emits=emits)
    assert defn.emits[0].event == "reply"
    assert defn.emits[0].model is Reply
    assert defn.emits[0].description == "A reply"


def test_broadcasts_metadata_stored_on_definition() -> None:
    bc = [Broadcasts(event="msg", room="general", description="broadcast")]
    defn = _make_def(broadcasts=bc)
    assert defn.broadcasts[0].event == "msg"
    assert defn.broadcasts[0].room == "general"


def test_deprecated_flag_stored_on_definition() -> None:
    defn = _make_def(deprecated=True)
    assert defn.deprecated is True


def test_ordered_flag_stored_on_definition() -> None:
    defn = _make_def(ordered=True)
    assert defn.ordered is True


def test_executor_flag_stored_on_definition() -> None:
    defn = _make_def(executor=True)
    assert defn.executor is True


def test_description_stored_on_definition() -> None:
    defn = _make_def(description="My description")
    assert defn.description == "My description"


def test_tags_stored_on_definition() -> None:
    defn = _make_def(tags=["chat", "room"])
    assert "chat" in defn.tags
    assert "room" in defn.tags


def test_payload_model_stored_when_provided() -> None:
    class Msg(BaseModel):
        text: str

    defn = _make_def(payload_model=Msg)
    assert defn.payload_model is Msg


def test_payload_model_is_none_when_not_provided() -> None:
    defn = _make_def()
    assert defn.payload_model is None
