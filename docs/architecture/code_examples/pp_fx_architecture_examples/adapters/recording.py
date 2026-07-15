"""Technology-free tracing decorators for explaining orchestration order."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..application.contracts.datasets import (
    DatasetBinding,
    LoadedDataset,
    ParameterBinding,
    ParameterSet,
)
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
from ..application.ports.gateways import (
    CompiledPlanRepository,
    DatasetGateway,
    ParameterGateway,
)
from ..application.ports.plugins import PluginExecutionPort
from ..application.ports.processing import (
    ContextExpander,
    DatasetAligner,
    DatasetNormalizer,
    ScopeResolver,
)


@dataclass(slots=True)
class CallTrace:
    events: list[str] = field(default_factory=list)

    def record(self, event: str) -> None:
        self.events.append(event)


class TracingCompiledPlanRepository:
    def __init__(
        self,
        delegate: CompiledPlanRepository,
        trace: CallTrace,
    ) -> None:
        self._delegate = delegate
        self._trace = trace

    def get(self, plan_id: CompiledPlanId) -> CompiledPlan:
        self._trace.record(f"plan.get:{plan_id.value}")
        return self._delegate.get(plan_id)


class TracingDatasetGateway:
    def __init__(self, delegate: DatasetGateway, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def load(self, binding: DatasetBinding) -> LoadedDataset:
        self._trace.record(f"dataset.load:{binding.role.value}")
        return self._delegate.load(binding)


class TracingParameterGateway:
    def __init__(self, delegate: ParameterGateway, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def load(self, binding: ParameterBinding) -> ParameterSet:
        self._trace.record(f"parameters.load:{binding.parameter_set.value}")
        return self._delegate.load(binding)


class TracingDatasetNormalizer:
    def __init__(self, delegate: DatasetNormalizer, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def normalize(self, request: NormalizationRequest) -> NormalizationResult:
        self._trace.record(f"dataset.normalize:{request.dataset.binding.role.value}")
        return self._delegate.normalize(request)


class TracingScopeResolver:
    def __init__(self, delegate: ScopeResolver, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def resolve(self, request: ScopeResolutionRequest) -> ScopeResolutionResult:
        self._trace.record(f"scope.resolve:{request.dataset.binding.role.value}")
        return self._delegate.resolve(request)


class TracingContextExpander:
    def __init__(self, delegate: ContextExpander, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def expand(self, request: ContextExpansionRequest) -> ContextExpansionResult:
        self._trace.record(f"context.expand:{request.dataset.binding.role.value}")
        return self._delegate.expand(request)


class TracingDatasetAligner:
    def __init__(self, delegate: DatasetAligner, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def align(self, request: DatasetAlignmentRequest) -> AlignedDatasets:
        self._trace.record("datasets.align")
        return self._delegate.align(request)


class TracingPluginExecutor:
    def __init__(self, delegate: PluginExecutionPort, trace: CallTrace) -> None:
        self._delegate = delegate
        self._trace = trace

    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult:
        self._trace.record(f"plugin.execute:{node.id.value}")
        return self._delegate.execute(node, data)
