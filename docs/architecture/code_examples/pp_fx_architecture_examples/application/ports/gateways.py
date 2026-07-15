"""Gateway and repository capabilities required by application services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts.datasets import (
    DatasetBinding,
    LoadedDataset,
    ParameterBinding,
    ParameterSet,
)
from ..contracts.plans import CompiledPlan, CompiledPlanId


@runtime_checkable
class DatasetGateway(Protocol):
    def load(self, binding: DatasetBinding) -> LoadedDataset: ...


@runtime_checkable
class ParameterGateway(Protocol):
    def load(self, binding: ParameterBinding) -> ParameterSet: ...


@runtime_checkable
class CompiledPlanRepository(Protocol):
    def get(self, plan_id: CompiledPlanId) -> CompiledPlan: ...
