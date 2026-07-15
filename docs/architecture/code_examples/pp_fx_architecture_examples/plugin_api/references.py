from __future__ import annotations

from dataclasses import dataclass


def _require_reference_value(value: str, kind: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{kind} must be a non-empty, trimmed value.")


@dataclass(frozen=True, slots=True)
class ChannelRef:
    """Plugin-owned reference to a canonical sampled channel."""

    value: str

    def __post_init__(self) -> None:
        _require_reference_value(self.value, "ChannelRef")


@dataclass(frozen=True, slots=True)
class ParameterRef:
    """Plugin-owned reference to a canonical request parameter."""

    value: str

    def __post_init__(self) -> None:
        _require_reference_value(self.value, "ParameterRef")


@dataclass(frozen=True, slots=True)
class QuantityRef:
    """Plugin-owned physical-quantity reference."""

    value: str

    def __post_init__(self) -> None:
        _require_reference_value(self.value, "QuantityRef")


@dataclass(frozen=True, slots=True)
class UnitRef:
    """Plugin-owned unit reference carrying its declared quantity."""

    value: str
    quantity: QuantityRef

    def __post_init__(self) -> None:
        _require_reference_value(self.value, "UnitRef")
