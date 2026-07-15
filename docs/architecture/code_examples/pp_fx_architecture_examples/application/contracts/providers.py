"""Serializable plan, catalog, and function-pack provider contracts."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.identifiers import (
    CalculationNodeId,
    CatalogId,
    FunctionPackId,
    PlanId,
)
from .plans import CatalogLock, FunctionPackLock, ProcessingTarget


@dataclass(frozen=True, slots=True)
class PlanReference:
    id: PlanId
    version_range: str

    def __post_init__(self) -> None:
        if not self.version_range:
            raise ValueError("A plan reference requires a version range.")


@dataclass(frozen=True, slots=True)
class FunctionPackRequest:
    id: FunctionPackId
    version_range: str

    def __post_init__(self) -> None:
        if not self.version_range:
            raise ValueError("A function-pack request requires a version range.")


@dataclass(frozen=True, slots=True)
class CatalogRequest:
    id: CatalogId
    version_range: str

    def __post_init__(self) -> None:
        if not self.version_range:
            raise ValueError("A catalog request requires a version range.")


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    reference: PlanReference
    function_packs: tuple[FunctionPackRequest, ...]
    catalogs: tuple[CatalogRequest, ...]
    targets: tuple[ProcessingTarget, ...]

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("A processing-plan definition requires public targets.")


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    lock: CatalogLock


@dataclass(frozen=True, slots=True)
class FunctionPackSnapshot:
    lock: FunctionPackLock
    node_ids: tuple[CalculationNodeId, ...]

    def __post_init__(self) -> None:
        if len(self.node_ids) != len(set(self.node_ids)):
            raise ValueError("Function-pack snapshot node IDs must be unique.")
