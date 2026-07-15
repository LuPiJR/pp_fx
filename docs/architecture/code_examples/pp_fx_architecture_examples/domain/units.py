"""Immutable quantity and unit values without a unit-framework dependency."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

_QUANTITY_KIND = re.compile(r"^[a-z][a-z0-9_]*$")
_UNIT_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


@dataclass(frozen=True, slots=True)
class QuantityKind:
    """Physical dimension or semantic quantity, such as distance or pressure."""

    value: str

    def __post_init__(self) -> None:
        if not _QUANTITY_KIND.fullmatch(self.value):
            raise ValueError("A quantity kind must be one lowercase identifier segment.")


@dataclass(frozen=True, slots=True)
class Unit:
    """A named unit tied to exactly one quantity kind."""

    key: str
    symbol: str
    quantity_kind: QuantityKind

    def __post_init__(self) -> None:
        if not _UNIT_KEY.fullmatch(self.key):
            raise ValueError("A unit key must be a qualified lowercase canonical value.")
        if not self.symbol or self.symbol != self.symbol.strip():
            raise ValueError("A unit symbol must be non-empty and trimmed.")


@dataclass(frozen=True, slots=True)
class Quantity:
    """A finite decimal magnitude that can never exist without its unit."""

    magnitude: Decimal
    unit: Unit

    def __post_init__(self) -> None:
        if not isinstance(self.magnitude, Decimal):
            raise TypeError("A quantity magnitude must be a Decimal at this boundary.")
        if not self.magnitude.is_finite():
            raise ValueError("A quantity magnitude must be finite.")

    def uses_same_unit_as(self, other: Quantity) -> bool:
        return self.unit == other.unit
