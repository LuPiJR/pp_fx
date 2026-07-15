"""Requested and resolved coordinate scopes with explicit ancestry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import ChannelId, ScopeId
from .units import Quantity, QuantityKind, Unit


class BoundaryMode(StrEnum):
    EXACT = "exact"
    INTERPOLATE = "interpolate"
    NEAREST = "nearest"


@dataclass(frozen=True, slots=True)
class CoordinateAxis:
    """Semantic coordinate identity and its canonical quantity contract."""

    id: ChannelId
    quantity_kind: QuantityKind
    canonical_unit: Unit

    def __post_init__(self) -> None:
        if self.canonical_unit.quantity_kind != self.quantity_kind:
            raise ValueError("A coordinate axis unit must match its quantity kind.")


@dataclass(frozen=True, slots=True)
class RequestedScope:
    """The caller's coordinate interval before adapter boundary resolution."""

    id: ScopeId
    axis: CoordinateAxis
    start: Quantity
    end: Quantity

    def __post_init__(self) -> None:
        _require_increasing_bounds(self.start, self.end)
        if self.start.unit.quantity_kind != self.axis.quantity_kind:
            raise ValueError("Scope bounds must match the axis quantity kind.")


@dataclass(frozen=True, slots=True)
class ResolvedScope:
    """Effective bounds plus the immutable parent scope that constrains them."""

    requested: RequestedScope
    effective_start: Quantity
    effective_end: Quantity
    boundary_mode: BoundaryMode
    parent: ResolvedScope | None = None

    def __post_init__(self) -> None:
        _require_increasing_bounds(self.effective_start, self.effective_end)
        _require_same_unit(self.requested.start, self.effective_start)
        _require_same_unit(self.requested.end, self.effective_end)

        if self.boundary_mode is BoundaryMode.EXACT and (
            self.effective_start != self.requested.start
            or self.effective_end != self.requested.end
        ):
            raise ValueError("Exact scope bounds must equal the requested bounds.")

        if self.parent is None:
            return
        if self.requested.axis != self.parent.requested.axis:
            raise ValueError("A child scope must use the same axis as its parent.")
        if self.id in self.parent.ancestry:
            raise ValueError("A child scope ID must be unique in its ancestry.")

        _require_inside_parent(
            self.requested.start,
            self.requested.end,
            self.parent,
        )
        _require_inside_parent(
            self.effective_start,
            self.effective_end,
            self.parent,
        )

    @property
    def id(self) -> ScopeId:
        return self.requested.id

    @property
    def ancestry(self) -> tuple[ScopeId, ...]:
        if self.parent is None:
            return (self.id,)
        return (*self.parent.ancestry, self.id)


def _require_increasing_bounds(start: Quantity, end: Quantity) -> None:
    _require_same_unit(start, end)
    if start.magnitude >= end.magnitude:
        raise ValueError("A coordinate scope requires start before end.")


def _require_same_unit(left: Quantity, right: Quantity) -> None:
    if not left.uses_same_unit_as(right):
        raise ValueError("Scope bounds must use the same unit; conversion is explicit.")


def _require_inside_parent(
    start: Quantity,
    end: Quantity,
    parent: ResolvedScope,
) -> None:
    _require_same_unit(start, parent.effective_start)
    _require_same_unit(end, parent.effective_end)
    if (
        start.magnitude < parent.effective_start.magnitude
        or end.magnitude > parent.effective_end.magnitude
    ):
        raise ValueError("A child scope must remain inside its parent.")
