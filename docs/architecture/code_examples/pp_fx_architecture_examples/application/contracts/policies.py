"""Request-selected processing policies with no adapter technology."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...domain.scopes import BoundaryMode


class OutOfRangeMode(StrEnum):
    REJECT = "reject"
    EXTRAPOLATE = "extrapolate"


class AlignmentPolicy(StrEnum):
    EXACT = "exact"
    NEAREST = "nearest"
    INTERPOLATE = "interpolate"


class NormalizationPolicy(StrEnum):
    STRICT = "strict"
    EXPLICIT = "explicit"


@dataclass(frozen=True, slots=True)
class BoundaryPolicy:
    mode: BoundaryMode
    out_of_range: OutOfRangeMode
