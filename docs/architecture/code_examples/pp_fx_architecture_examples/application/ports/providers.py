"""Versioned source-provider capabilities used during plan resolution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts.providers import (
    CatalogRequest,
    CatalogSnapshot,
    FunctionPackRequest,
    FunctionPackSnapshot,
    PlanDefinition,
    PlanReference,
)


@runtime_checkable
class PlanProvider(Protocol):
    def get(self, reference: PlanReference) -> PlanDefinition: ...


@runtime_checkable
class CatalogProvider(Protocol):
    def get(self, request: CatalogRequest) -> CatalogSnapshot: ...


@runtime_checkable
class FunctionPackProvider(Protocol):
    def get(self, request: FunctionPackRequest) -> FunctionPackSnapshot: ...
