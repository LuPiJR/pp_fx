"""Deterministic technology-free fakes for application service examples."""

from __future__ import annotations

from ..application.contracts.datasets import (
    DatasetBinding,
    LoadedDataset,
    ParameterBinding,
    ParameterSet,
)
from ..application.contracts.exports import ExportOutcome, ExportRequest
from ..application.contracts.operations import (
    AlignedDatasets,
    ContextExpansionRequest,
    ContextExpansionResult,
    DatasetAlignmentRequest,
    NormalizationRequest,
    NormalizationResult,
    PluginExecutionResult,
    PreparedNodeInput,
    ScopeResolutionRequest,
    ScopeResolutionResult,
)
from ..application.contracts.plans import CompiledNodeSpec, CompiledPlan, CompiledPlanId
from ..application.contracts.providers import (
    CatalogRequest,
    CatalogSnapshot,
    FunctionPackRequest,
    FunctionPackSnapshot,
    PlanDefinition,
    PlanReference,
)
from .plugin_mapping.registry import CallableBindingKey, CallableRegistry


class FakeDatasetGateway:
    def __init__(self, datasets: tuple[LoadedDataset, ...]) -> None:
        self.datasets = datasets
        self.calls: list[DatasetBinding] = []

    def load(self, binding: DatasetBinding) -> LoadedDataset:
        self.calls.append(binding)
        for dataset in self.datasets:
            if dataset.binding == binding:
                return dataset
        raise KeyError(binding)


class FakeParameterGateway:
    def __init__(self, parameter_sets: tuple[ParameterSet, ...]) -> None:
        self.parameter_sets = parameter_sets
        self.calls: list[ParameterBinding] = []

    def load(self, binding: ParameterBinding) -> ParameterSet:
        self.calls.append(binding)
        for parameter_set in self.parameter_sets:
            if parameter_set.reference == binding.parameter_set:
                return parameter_set
        raise KeyError(binding.parameter_set)


class FakeCompiledPlanRepository:
    def __init__(self, plans: tuple[CompiledPlan, ...]) -> None:
        self.plans = plans
        self.calls: list[CompiledPlanId] = []

    def get(self, plan_id: CompiledPlanId) -> CompiledPlan:
        self.calls.append(plan_id)
        for plan in self.plans:
            if plan.id == plan_id:
                return plan
        raise KeyError(plan_id)


class FakeScopeResolver:
    def __init__(self, result: ScopeResolutionResult) -> None:
        self.result = result
        self.calls: list[ScopeResolutionRequest] = []

    def resolve(self, request: ScopeResolutionRequest) -> ScopeResolutionResult:
        self.calls.append(request)
        return self.result


class FakeDatasetNormalizer:
    def __init__(self, result: NormalizationResult) -> None:
        self.result = result
        self.calls: list[NormalizationRequest] = []

    def normalize(self, request: NormalizationRequest) -> NormalizationResult:
        self.calls.append(request)
        return self.result


class FakeContextExpander:
    def __init__(self, result: ContextExpansionResult) -> None:
        self.result = result
        self.calls: list[ContextExpansionRequest] = []

    def expand(self, request: ContextExpansionRequest) -> ContextExpansionResult:
        self.calls.append(request)
        return self.result


class FakeDatasetAligner:
    def __init__(self, result: AlignedDatasets) -> None:
        self.result = result
        self.calls: list[DatasetAlignmentRequest] = []

    def align(self, request: DatasetAlignmentRequest) -> AlignedDatasets:
        self.calls.append(request)
        return self.result


class FakePluginExecutor:
    def __init__(self, result: PluginExecutionResult) -> None:
        self.result = result
        self.calls: list[tuple[CompiledNodeSpec, PreparedNodeInput]] = []

    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult:
        self.calls.append((node, data))
        if self.result.node_id != node.id:
            raise ValueError("The fake plugin result must belong to the requested node.")
        return self.result


class RegistryBackedFakePluginExecutor:
    """Resolves an exact locked binding and invokes only a canned example callable."""

    def __init__(self, registry: CallableRegistry) -> None:
        self._registry = registry
        self.calls: list[tuple[CompiledNodeSpec, PreparedNodeInput]] = []

    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult:
        self.calls.append((node, data))
        function = self._registry.resolve(CallableBindingKey.from_specification(node))
        result = function(node, data)
        if not isinstance(result, PluginExecutionResult):
            raise TypeError("A canned registry callable must return PluginExecutionResult.")
        if result.node_id != node.id:
            raise ValueError("A registry result must belong to the resolved node.")
        return result


class FakePlanProvider:
    def __init__(self, definitions: tuple[PlanDefinition, ...]) -> None:
        self.definitions = definitions
        self.calls: list[PlanReference] = []

    def get(self, reference: PlanReference) -> PlanDefinition:
        self.calls.append(reference)
        for definition in self.definitions:
            if definition.reference == reference:
                return definition
        raise KeyError(reference)


class FakeCatalogProvider:
    def __init__(self, snapshots: tuple[CatalogSnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.calls: list[CatalogRequest] = []

    def get(self, request: CatalogRequest) -> CatalogSnapshot:
        self.calls.append(request)
        for snapshot in self.snapshots:
            if snapshot.lock.id == request.id:
                return snapshot
        raise KeyError(request)


class FakeFunctionPackProvider:
    def __init__(self, snapshots: tuple[FunctionPackSnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.calls: list[FunctionPackRequest] = []

    def get(self, request: FunctionPackRequest) -> FunctionPackSnapshot:
        self.calls.append(request)
        for snapshot in self.snapshots:
            if snapshot.lock.id == request.id:
                return snapshot
        raise KeyError(request)


class FakeReportExporter:
    def __init__(self, outcome: ExportOutcome) -> None:
        self.outcome = outcome
        self.calls: list[ExportRequest] = []

    def export(self, request: ExportRequest) -> ExportOutcome:
        self.calls.append(request)
        return self.outcome
