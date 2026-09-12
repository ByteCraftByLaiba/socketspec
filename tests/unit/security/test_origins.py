# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

"""Tests for OriginValidator."""

from __future__ import annotations

from socketspec.security.origins import OriginValidator


def test_allowed_origin_returns_true() -> None:
    validator = OriginValidator(["http://localhost", "https://example.com"])
    assert validator.is_allowed("http://localhost") is True
    assert validator.is_allowed("https://example.com") is True


def test_disallowed_origin_returns_false() -> None:
    validator = OriginValidator(["http://localhost"])
    assert validator.is_allowed("https://example.com") is False


def test_wildcard_allows_any_origin() -> None:
    validator = OriginValidator(["*"])
    assert validator.is_allowed("http://localhost") is True
    assert validator.is_allowed("https://attacker.com") is True


def test_wildcard_allows_none_origin() -> None:
    validator = OriginValidator(["*"])
    assert validator.is_allowed(None) is True


def test_none_origin_rejected_when_not_wildcard() -> None:
    validator = OriginValidator(["http://localhost"])
    assert validator.is_allowed(None) is False


def test_empty_allowed_origins_rejects_everything() -> None:
    validator = OriginValidator([])
    assert validator.is_allowed("http://localhost") is False
    assert validator.is_allowed(None) is False


def test_multiple_allowed_origins_all_pass() -> None:
    validator = OriginValidator(["http://a.com", "http://b.com", "http://c.com"])
    assert validator.is_allowed("http://a.com") is True
    assert validator.is_allowed("http://b.com") is True
    assert validator.is_allowed("http://c.com") is True
    assert validator.is_allowed("http://d.com") is False


def test_origin_check_is_case_sensitive() -> None:
    validator = OriginValidator(["http://Example.com"])
    assert validator.is_allowed("http://Example.com") is True
    assert validator.is_allowed("http://example.com") is False


def test_partial_origin_match_rejected() -> None:
    validator = OriginValidator(["http://example.com"])
    assert validator.is_allowed("http://example.com.attacker.com") is False
    assert validator.is_allowed("http://sub.example.com") is False
