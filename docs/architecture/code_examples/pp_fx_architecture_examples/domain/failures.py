"""Typed failure values; unexpected system failures are still raised by services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_FAILURE_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")


class FailureCategory(StrEnum):
    """Ownership and propagation level of a processing failure."""

    REQUEST = "request"
    NODE = "node"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class FailureDetail:
    """Transport-neutral failure information constrained by outer contracts."""

    category: FailureCategory
    code: str
    message: str

    def __post_init__(self) -> None:
        if not _FAILURE_CODE.fullmatch(self.code):
            raise ValueError("A failure code must use uppercase underscore notation.")
        if not self.message or self.message != self.message.strip():
            raise ValueError("A failure message must be non-empty and trimmed.")
