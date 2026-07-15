from __future__ import annotations

import ast
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

import pytest

from pp_fx_architecture_examples.adapters.fakes import (
    FakeCompiledPlanRepository,
    FakeContextExpander,
    FakeDatasetAligner,
    FakeDatasetGateway,
    FakeDatasetNormalizer,
    FakeParameterGateway,
    FakeScopeResolver,
)
from pp_fx_architecture_examples.adapters.recording import (
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
from pp_fx_architecture_examples.application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
    DatasetFingerprint,
    LoadedDataset,
    ParameterBinding,
    ParameterSet,
)
from pp_fx_architecture_examples.application.contracts.operations import (
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
from pp_fx_architecture_examples.application.contracts.plans import (
    CompiledGraph,
    CompiledNodeKind,
    CompiledNodeSpec,
    CompiledPlan,
    ContentHash,
    FunctionPackLock,
    GraphNodeSpec,
    ProcessingTarget,
)
from pp_fx_architecture_examples.application.contracts.policies import (
    AlignmentPolicy,
    BoundaryPolicy,
    NormalizationPolicy,
    OutOfRangeMode,
)
from pp_fx_architecture_examples.application.contracts.reports import (
    ExecutionCompleted,
    ReportStatus,
    RequestRejected,
)
from pp_fx_architecture_examples.application.contracts.requests import ProcessingRequest
from pp_fx_architecture_examples.application.contracts.tables import TableHandle
from pp_fx_architecture_examples.application.ports.plugins import PluginExecutionPort
from pp_fx_architecture_examples.application.ports.use_cases import ProcessDataset
from pp_fx_architecture_examples.application.services.graph_compiler import (
    compile_static_graph,
)
from pp_fx_architecture_examples.application.services.process_dataset import (
    ProcessDatasetService,
)
from pp_fx_architecture_examples.domain.failures import FailureCategory, FailureDetail
from pp_fx_architecture_examples.domain.graph import (
    ArtifactInput,
    ArtifactKind,
    ArtifactOutput,
    ArtifactSource,
    ScopeEdgeMode,
)
from pp_fx_architecture_examples.domain.identifiers import (
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
from pp_fx_architecture_examples.domain.results import (
    ArtifactResult,
    NodeStatus,
    ResultProvenance,
)
from pp_fx_architecture_examples.domain.scopes import (
    BoundaryMode,
    CoordinateAxis,
    RequestedScope,
    ResolvedScope,
)
from pp_fx_architecture_examples.domain.units import Quantity, QuantityKind, Unit

SERVICES_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/application/services"
)
DISTANCE = QuantityKind("distance")
METRE = Unit("si.metre", "m", DISTANCE)
RAW = ArtifactId("raw.vehicle.speed")
OUTPUT = ArtifactId("result.vehicle.speed.maximum")
PACK = FunctionPackLock(
    id=FunctionPackId("pack.example"),
    version="1.0.0",
    distribution_hash=ContentHash("sha256", "a" * 64),
    declaration_hash=ContentHash("sha256", "b" * 64),
)
BINDING = DatasetBinding(
    role=DatasetRole("primary"),
    dataset=DatasetReference("dataset-primary"),
    ingestion_profile=IngestionProfileReference("example.in_memory_v1"),
)
PARAMETER_BINDING = ParameterBinding(ParameterSetReference("parameters-example"))
PARAMETERS = ParameterSet(PARAMETER_BINDING.parameter_set, ())
LOADED = LoadedDataset(
    binding=BINDING,
    table=TableHandle("request-1/primary"),
    fingerprint=DatasetFingerprint("sha256:" + "c" * 64),
)
REQUESTED_SCOPE = RequestedScope(
    id=ScopeId("scope.selection"),
    axis=CoordinateAxis(ChannelId("lap.distance"), DISTANCE, METRE),
    start=Quantity(Decimal("500"), METRE),
    end=Quantity(Decimal("700"), METRE),
)
ExecutorT = TypeVar("ExecutorT", bound=PluginExecutionPort)
RESOLVED_SCOPE = ResolvedScope(
    requested=REQUESTED_SCOPE,
    effective_start=REQUESTED_SCOPE.start,
    effective_end=REQUESTED_SCOPE.end,
    boundary_mode=BoundaryMode.EXACT,
)


def test_happy_path_executes_in_port_order_and_returns_completed_report() -> None:
    node = graph_node("example.maximum", (RAW,), OUTPUT)
    plan = compiled_plan((node,), (OUTPUT,))
    execution = successful_execution(node.specification, OUTPUT)
    trace = CallTrace()
    service, executor = service_fixture(plan, ResultByNodeExecutor({node.specification.id: execution}), trace)

    outcome = service.execute(processing_request())

    assert isinstance(service, ProcessDataset)
    assert isinstance(outcome, ExecutionCompleted)
    assert outcome.report.status is ReportStatus.SUCCESS
    assert outcome.report.results[0].artifact == execution.scalar_results[0]
    assert outcome.report.instances[0].status is NodeStatus.SUCCEEDED
    assert executor.calls == [node.specification.id]
    assert trace.events == [
        "plan.get:plan.example",
        "dataset.load:primary",
        "parameters.load:parameters-example",
        "dataset.normalize:primary",
        "scope.resolve:primary",
        "context.expand:primary",
        "datasets.align",
        "plugin.execute:example.maximum",
    ]


def test_successful_upstream_artifact_is_passed_to_its_descendant() -> None:
    upstream_artifact = ArtifactId("result.upstream.value")
    final_artifact = ArtifactId("result.final.value")
    upstream = graph_node("example.upstream", (RAW,), upstream_artifact)
    descendant = graph_node(
        "example.descendant",
        (upstream_artifact,),
        final_artifact,
    )
    plan = compiled_plan((upstream, descendant), (final_artifact,))
    upstream_result = successful_execution(upstream.specification, upstream_artifact)
    executor = ResultByNodeExecutor(
        {
            upstream.specification.id: upstream_result,
            descendant.specification.id: successful_execution(
                descendant.specification,
                final_artifact,
            ),
        }
    )
    service, executor = service_fixture(plan, executor, CallTrace())

    outcome = service.execute(processing_request())

    assert isinstance(outcome, ExecutionCompleted)
    assert executor.inputs[descendant.specification.id].scalar_artifacts == (
        upstream_result.scalar_results[0],
    )


def test_unknown_target_is_rejected_before_loading_or_node_execution() -> None:
    node = graph_node("example.maximum", (RAW,), OUTPUT)
    plan = compiled_plan((node,), (OUTPUT,))
    trace = CallTrace()
    service, executor = service_fixture(plan, ResultByNodeExecutor({}), trace)
    invalid_request = replace(
        processing_request(),
        targets=(ProcessingTargetId("target.unknown"),),
    )

    outcome = service.execute(invalid_request)

    assert isinstance(outcome, RequestRejected)
    assert tuple(failure.code for failure in outcome.failures) == ("UNKNOWN_TARGET",)
    assert executor.calls == []
    assert trace.events == ["plan.get:plan.example"]


def test_node_failure_blocks_only_descendants_and_report_is_partial() -> None:
    failed_artifact = ArtifactId("result.failed.root")
    child_artifact = ArtifactId("result.failed.child")
    independent_artifact = ArtifactId("result.independent.value")
    failed = graph_node("example.failed", (RAW,), failed_artifact)
    child = graph_node("example.child", (failed_artifact,), child_artifact)
    independent = graph_node("example.independent", (RAW,), independent_artifact)
    plan = compiled_plan(
        (failed, child, independent),
        (child_artifact, independent_artifact),
    )
    node_failure = FailureDetail(
        FailureCategory.NODE,
        "PLUGIN_EXCEPTION",
        "The plugin failed for this node.",
    )
    executions = {
        failed.specification.id: PluginExecutionResult(
            node_id=failed.specification.id,
            scalar_results=(
                ArtifactResult(
                    artifact_id=failed_artifact,
                    status=NodeStatus.FAILED,
                    failure=node_failure,
                ),
            ),
            table_artifacts=(),
        ),
        independent.specification.id: successful_execution(
            independent.specification,
            independent_artifact,
        ),
    }
    trace = CallTrace()
    service, executor = service_fixture(plan, ResultByNodeExecutor(executions), trace)

    outcome = service.execute(processing_request())

    assert isinstance(outcome, ExecutionCompleted)
    assert outcome.report.status is ReportStatus.PARTIAL_SUCCESS
    statuses = {record.node_id: record for record in outcome.report.instances}
    assert statuses[failed.specification.id].status is NodeStatus.FAILED
    assert statuses[independent.specification.id].status is NodeStatus.SUCCEEDED
    assert statuses[child.specification.id].status is NodeStatus.NOT_CALCULATED
    assert statuses[child.specification.id].failure is not None
    assert statuses[child.specification.id].failure.code == "DEPENDENCY_FAILED"
    assert executor.calls == [failed.specification.id, independent.specification.id]
    assert tuple(record.artifact.artifact_id for record in outcome.report.results) == (
        independent_artifact,
    )


def test_unexpected_system_failure_remains_raised() -> None:
    node = graph_node("example.maximum", (RAW,), OUTPUT)
    plan = compiled_plan((node,), (OUTPUT,))
    trace = CallTrace()
    service, _ = service_fixture(
        plan,
        RaisingPluginExecutor(RuntimeError("workspace invariant broken")),
        trace,
    )

    with pytest.raises(RuntimeError, match="workspace invariant broken"):
        service.execute(processing_request())

    assert trace.events[-1] == "plugin.execute:example.maximum"


def test_application_services_import_no_adapters_plugin_api_or_pandas() -> None:
    violations: list[str] = []

    for source_file in sorted(SERVICES_ROOT.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = (node.module,)
            else:
                imported = ()
            for name in imported:
                if any(
                    forbidden in name.split(".")
                    for forbidden in ("adapters", "plugin_api", "pandas")
                ):
                    violations.append(f"{source_file.name}:{node.lineno}:{name}")

    assert violations == []


def graph_node(
    node_id: str,
    inputs: tuple[ArtifactId, ...],
    output: ArtifactId,
) -> GraphNodeSpec:
    input_contracts = tuple(
        ArtifactInput(
            artifact=artifact,
            kind=(
                ArtifactKind.RAW_CHANNEL
                if artifact == RAW
                else ArtifactKind.SCALAR_KPI
            ),
            scope_mode=ScopeEdgeMode.SAME_SCOPE,
        )
        for artifact in inputs
    )
    specification = CompiledNodeSpec(
        id=CalculationNodeId(node_id),
        pack=PACK,
        consumes=inputs,
        produces=(output,),
        kind=CompiledNodeKind.KPI,
    )
    return GraphNodeSpec(
        specification=specification,
        inputs=input_contracts,
        outputs=(ArtifactOutput(output, ArtifactKind.SCALAR_KPI),),
    )


def compiled_plan(
    nodes: tuple[GraphNodeSpec, ...],
    exports: tuple[ArtifactId, ...],
) -> CompiledPlan:
    compilation = compile_static_graph(
        sources=(ArtifactSource(ArtifactOutput(RAW, ArtifactKind.RAW_CHANNEL)),),
        nodes=nodes,
        targets=(ProcessingTarget(ProcessingTargetId("target.analysis"), exports),),
    )
    assert compilation.graph is not None
    return CompiledPlan(
        id=CompiledPlanId("plan.example"),
        plugin_api_version="1.0",
        unit_registry_version="2026.1",
        function_packs=(PACK,),
        catalogs=(),
        graph=compilation.graph,
    )


def processing_request() -> ProcessingRequest:
    return ProcessingRequest(
        compiled_plan=CompiledPlanId("plan.example"),
        datasets=DatasetBindings((BINDING,)),
        parameters=PARAMETER_BINDING,
        targets=(ProcessingTargetId("target.analysis"),),
        scope=REQUESTED_SCOPE,
        boundary_policy=BoundaryPolicy(BoundaryMode.EXACT, OutOfRangeMode.REJECT),
        alignment_policy=AlignmentPolicy.EXACT,
        normalization_policy=NormalizationPolicy.STRICT,
    )


def successful_execution(
    node: CompiledNodeSpec,
    artifact: ArtifactId,
) -> PluginExecutionResult:
    result = ArtifactResult(
        artifact_id=artifact,
        status=NodeStatus.SUCCEEDED,
        value=Quantity(Decimal("42"), METRE),
        provenance=ResultProvenance(
            node_id=node.id,
            input_artifacts=node.consumes,
            calculation_unit=METRE,
        ),
    )
    return PluginExecutionResult(node.id, (result,), ())


def service_fixture(
    plan: CompiledPlan,
    executor: ExecutorT,
    trace: CallTrace,
) -> tuple[ProcessDatasetService, ExecutorT]:
    normalized = NormalizationResult(LOADED, NormalizationReport(()))
    scoped = ScopeResolutionResult(LOADED, RESOLVED_SCOPE)
    context = ContextExpansionResult(LOADED, RESOLVED_SCOPE, 0, 0)
    aligned = AlignedDatasets(
        (RoleTable(DatasetRole("primary"), LOADED.table),),
        AlignmentReport(()),
    )
    service = ProcessDatasetService(
        plans=TracingCompiledPlanRepository(
            FakeCompiledPlanRepository((plan,)),
            trace,
        ),
        datasets=TracingDatasetGateway(FakeDatasetGateway((LOADED,)), trace),
        parameters=TracingParameterGateway(FakeParameterGateway((PARAMETERS,)), trace),
        normalizer=TracingDatasetNormalizer(FakeDatasetNormalizer(normalized), trace),
        scopes=TracingScopeResolver(FakeScopeResolver(scoped), trace),
        contexts=TracingContextExpander(FakeContextExpander(context), trace),
        aligner=TracingDatasetAligner(FakeDatasetAligner(aligned), trace),
        plugins=TracingPluginExecutor(executor, trace),
    )
    return service, executor


class ResultByNodeExecutor:
    def __init__(
        self,
        results: dict[CalculationNodeId, PluginExecutionResult],
    ) -> None:
        self._results = results
        self.calls: list[CalculationNodeId] = []
        self.inputs: dict[CalculationNodeId, PreparedNodeInput] = {}

    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult:
        self.calls.append(node.id)
        self.inputs[node.id] = data
        return self._results[node.id]


class RaisingPluginExecutor:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult:
        raise self._error
