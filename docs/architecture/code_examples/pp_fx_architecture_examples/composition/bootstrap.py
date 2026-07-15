"""One explicit architecture-example composition root and request lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from types import TracebackType

import pandas as pd

from ..adapters.fakes import (
    FakeCompiledPlanRepository,
    FakeContextExpander,
    FakeDatasetAligner,
    FakeDatasetGateway,
    FakeDatasetNormalizer,
    FakeParameterGateway,
    FakeScopeResolver,
    RegistryBackedFakePluginExecutor,
)
from ..adapters.pandas_tables.workspace import PandasTableWorkspace
from ..adapters.plugin_mapping.registry import (
    CallableBindingKey,
    InMemoryCallableRegistry,
)
from ..adapters.recording import (
    CallTrace,
    TracingCompiledPlanRepository,
    TracingContextExpander,
    TracingDatasetAligner,
    TracingDatasetGateway,
    TracingDatasetNormalizer,
    TracingParameterGateway,
    TracingPluginExecutor,
    TracingScopeResolver,
)
from ..application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
    DatasetFingerprint,
    LoadedDataset,
    ParameterBinding,
    ParameterSet,
)
from ..application.contracts.operations import (
    AlignedDatasets,
    AlignmentReport,
    ContextExpansionResult,
    NormalizationReport,
    NormalizationResult,
    PluginExecutionResult,
    PreparedNodeInput,
    RoleTable,
    ScopeResolutionResult,
)
from ..application.contracts.plans import (
    CompiledNodeKind,
    CompiledNodeSpec,
    CompiledPlan,
    ContentHash,
    FunctionPackLock,
    GraphNodeSpec,
    ProcessingTarget,
)
from ..application.contracts.reports import ProcessOutcome
from ..application.services.graph_compiler import compile_static_graph
from ..application.services.process_dataset import ProcessDatasetService
from ..delivery.python_facade import PythonProcessingFacade
from ..delivery.request_dtos import (
    PythonDatasetInput,
    PythonParameterInput,
    PythonProcessInput,
    PythonScopeInput,
)
from ..delivery.request_mapping import PythonRequestBuilder, RequestValueCatalog
from ..domain.graph import (
    ArtifactInput,
    ArtifactKind,
    ArtifactOutput,
    ArtifactSource,
    ScopeEdgeMode,
)
from ..domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    ChannelId,
    CompiledPlanId,
    DatasetReference,
    DatasetRole,
    FunctionPackId,
    IngestionProfileReference,
    ParameterSetReference,
    ProcessingTargetId,
    ScopeId,
)
from ..domain.results import ArtifactResult, NodeStatus, ResultProvenance
from ..domain.scopes import BoundaryMode, CoordinateAxis, RequestedScope, ResolvedScope
from ..domain.units import Quantity, QuantityKind, Unit

_DISTANCE = QuantityKind("distance")
_SPEED = QuantityKind("speed")
_METRE = Unit("si.metre", "m", _DISTANCE)
_METRES_PER_SECOND = Unit("si.metre_per_second", "m/s", _SPEED)
_AXIS = CoordinateAxis(ChannelId("lap.distance"), _DISTANCE, _METRE)
_RAW_SPEED = ArtifactId("raw.vehicle.speed")
_MAXIMUM_SPEED = ArtifactId("result.vehicle.speed_maximum")
_NODE_ID = CalculationNodeId("example.speed_maximum")
_BINDING = DatasetBinding(
    role=DatasetRole("primary"),
    dataset=DatasetReference("dataset-example"),
    ingestion_profile=IngestionProfileReference("example.in_memory_v1"),
)
_PARAMETER_BINDING = ParameterBinding(ParameterSetReference("parameters-example"))
_REQUESTED_SCOPE = RequestedScope(
    id=ScopeId("scope.analysis"),
    axis=_AXIS,
    start=Quantity(Decimal("0"), _METRE),
    end=Quantity(Decimal("100"), _METRE),
)
_RESOLVED_SCOPE = ResolvedScope(
    requested=_REQUESTED_SCOPE,
    effective_start=_REQUESTED_SCOPE.start,
    effective_end=_REQUESTED_SCOPE.end,
    boundary_mode=BoundaryMode.EXACT,
)


@dataclass(frozen=True, slots=True)
class _StaticRequestCatalog(RequestValueCatalog):
    axis: CoordinateAxis
    units: tuple[Unit, ...]

    def resolve_axis(self, reference: str) -> CoordinateAxis | None:
        return self.axis if reference == self.axis.id.value else None

    def resolve_unit(self, reference: str) -> Unit | None:
        return next((unit for unit in self.units if unit.symbol == reference), None)


class ArchitectureExampleApplication:
    """Owns one composed facade and one request-scoped table workspace."""

    def __init__(
        self,
        facade: PythonProcessingFacade,
        workspace: PandasTableWorkspace,
        trace: CallTrace,
    ) -> None:
        self.facade = facade
        self.workspace = workspace
        self.trace = trace
        self._processed = False

    def __enter__(self) -> ArchitectureExampleApplication:
        if self.workspace.disposed:
            raise RuntimeError("The architecture-example application is already closed.")
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def process(self, request: PythonProcessInput) -> ProcessOutcome:
        if self.workspace.disposed:
            raise RuntimeError("The request-scoped composition is closed.")
        if self._processed:
            raise RuntimeError("Create a new composition for each processing request.")
        self._processed = True
        # Delivery layer: external Python values become one application request.
        self.trace.record("delivery.python_facade")
        # Application layer: the facade invokes ProcessDataset; injected ports drive outward.
        return self.facade.process(request)

    def close(self) -> None:
        if self.workspace.disposed:
            return
        # Composition layer: the outermost owner always releases request resources.
        self.workspace.dispose()
        self.trace.record("composition.workspace.dispose")


def compose_example_application() -> ArchitectureExampleApplication:
    """Construct every concrete dependency for one in-memory example request."""

    trace = CallTrace()
    workspace = PandasTableWorkspace(token_factory=lambda: "request_example")
    trace.record("composition.workspace.open")

    # Adapter layer: a pandas frame receives an opaque application-facing handle.
    table = workspace.store(
        pd.DataFrame({"lap.distance": [0.0, 100.0], "vehicle.speed": [40.0, 42.0]}),
        label="dataset-primary",
    )
    loaded = LoadedDataset(
        binding=_BINDING,
        table=table,
        fingerprint=DatasetFingerprint("sha256:" + "a" * 64),
    )
    parameters = ParameterSet(_PARAMETER_BINDING.parameter_set, ())
    plan, node = _compiled_plan()

    # Adapter layer: fakes satisfy driven ports; decorators expose the call sequence.
    plans = TracingCompiledPlanRepository(FakeCompiledPlanRepository((plan,)), trace)
    datasets = TracingDatasetGateway(FakeDatasetGateway((loaded,)), trace)
    parameter_gateway = TracingParameterGateway(
        FakeParameterGateway((parameters,)),
        trace,
    )
    normalizer = TracingDatasetNormalizer(
        FakeDatasetNormalizer(NormalizationResult(loaded, NormalizationReport(()))),
        trace,
    )
    scopes = TracingScopeResolver(
        FakeScopeResolver(ScopeResolutionResult(loaded, _RESOLVED_SCOPE)),
        trace,
    )
    contexts = TracingContextExpander(
        FakeContextExpander(
            ContextExpansionResult(loaded, _RESOLVED_SCOPE, 0, 0)
        ),
        trace,
    )
    aligner = TracingDatasetAligner(
        FakeDatasetAligner(
            AlignedDatasets(
                (RoleTable(DatasetRole("primary"), table),),
                AlignmentReport(()),
            )
        ),
        trace,
    )

    # Plugin adapter: exact plan-lock identity resolves a canned scalar result callable.
    registry = InMemoryCallableRegistry()
    registry.bind(CallableBindingKey.from_specification(node), _canned_scalar_result)
    plugins = TracingPluginExecutor(
        RegistryBackedFakePluginExecutor(registry),
        trace,
    )

    # Application layer: the use case receives protocols; it constructs no adapter.
    service = ProcessDatasetService(
        plans=plans,
        datasets=datasets,
        parameters=parameter_gateway,
        normalizer=normalizer,
        scopes=scopes,
        contexts=contexts,
        aligner=aligner,
        plugins=plugins,
    )

    # Delivery layer: the driving facade depends only on request mapping and input port.
    request_builder = PythonRequestBuilder(_StaticRequestCatalog(_AXIS, (_METRE,)))
    facade = PythonProcessingFacade(request_builder, service)
    return ArchitectureExampleApplication(facade, workspace, trace)


def successful_request() -> PythonProcessInput:
    return PythonProcessInput(
        compiled_plan="plan.example",
        datasets=(
            PythonDatasetInput("primary", "dataset-example", "example.in_memory_v1"),
        ),
        parameters=PythonParameterInput("parameters-example"),
        targets=("target.speed_maximum",),
        scope=PythonScopeInput(
            id="scope.analysis",
            axis="lap.distance",
            start=Decimal("0"),
            end=Decimal("100"),
            unit="m",
        ),
        boundary_mode="exact",
        out_of_range="reject",
        alignment="exact",
        normalization="strict",
    )


def unknown_target_request() -> PythonProcessInput:
    return replace(successful_request(), targets=("target.unknown",))


def _compiled_plan() -> tuple[CompiledPlan, CompiledNodeSpec]:
    pack = FunctionPackLock(
        id=FunctionPackId("pack.example"),
        version="1.0.0",
        distribution_hash=ContentHash("sha256", "b" * 64),
        declaration_hash=ContentHash("sha256", "c" * 64),
    )
    node = CompiledNodeSpec(
        id=_NODE_ID,
        pack=pack,
        consumes=(_RAW_SPEED,),
        produces=(_MAXIMUM_SPEED,),
        kind=CompiledNodeKind.KPI,
    )
    graph_node = GraphNodeSpec(
        specification=node,
        inputs=(
            ArtifactInput(
                _RAW_SPEED,
                ArtifactKind.RAW_CHANNEL,
                ScopeEdgeMode.SAME_SCOPE,
            ),
        ),
        outputs=(ArtifactOutput(_MAXIMUM_SPEED, ArtifactKind.SCALAR_KPI),),
    )
    compilation = compile_static_graph(
        sources=(
            ArtifactSource(ArtifactOutput(_RAW_SPEED, ArtifactKind.RAW_CHANNEL)),
        ),
        nodes=(graph_node,),
        targets=(
            ProcessingTarget(
                ProcessingTargetId("target.speed_maximum"),
                (_MAXIMUM_SPEED,),
            ),
        ),
    )
    if compilation.graph is None:
        raise RuntimeError("The fixed architecture-example graph must compile.")
    return (
        CompiledPlan(
            id=CompiledPlanId("plan.example"),
            plugin_api_version="1.0",
            unit_registry_version="2026.1",
            function_packs=(pack,),
            catalogs=(),
            graph=compilation.graph,
        ),
        node,
    )


def _canned_scalar_result(
    node: CompiledNodeSpec,
    data: PreparedNodeInput,
) -> PluginExecutionResult:
    """Return a fixed value; this walkthrough intentionally performs no calculation."""

    if data.scope != _RESOLVED_SCOPE:
        raise ValueError("The canned result accepts only the configured example scope.")
    artifact = ArtifactResult(
        artifact_id=_MAXIMUM_SPEED,
        status=NodeStatus.SUCCEEDED,
        value=Quantity(Decimal("42"), _METRES_PER_SECOND),
        provenance=ResultProvenance(node.id, node.consumes, _METRES_PER_SECOND),
    )
    return PluginExecutionResult(node.id, (artifact,), ())
