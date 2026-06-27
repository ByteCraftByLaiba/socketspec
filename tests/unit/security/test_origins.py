# Copyright (c) 2025 Laiba Shahab. All rights reserved.
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

from socketspec.security.origins import OriginValidator


def test_wildcard_allows_any_origin() -> None:
    validator = OriginValidator(["*"])
    assert validator.is_allowed("https://example.com") is True


def test_missing_origin_rejected_when_not_wildcard() -> None:
    validator = OriginValidator(["https://allowed.com"])
    assert validator.is_allowed(None) is False


def test_allowed_origin_passes_validation() -> None:
    validator = OriginValidator(["https://allowed.com"])
    assert validator.is_allowed("https://allowed.com") is True
