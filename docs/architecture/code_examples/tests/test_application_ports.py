from __future__ import annotations

import ast
import inspect
import sys
from decimal import Decimal
from pathlib import Path
from typing import get_type_hints

from pp_fx_architecture_examples.adapters.fakes import (
    FakeCatalogProvider,
    FakeCompiledPlanRepository,
    FakeContextExpander,
    FakeDatasetAligner,
    FakeDatasetGateway,
    FakeDatasetNormalizer,
    FakeFunctionPackProvider,
    FakeParameterGateway,
    FakePlanProvider,
    FakePluginExecutor,
    FakeReportExporter,
    FakeScopeResolver,
)
from pp_fx_architecture_examples.application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
    DatasetFingerprint,
    LoadedDataset,
    ParameterBinding,
    ParameterSet,
)
from pp_fx_architecture_examples.application.contracts.exports import (
    ExportDestination,
    ExportFormat,
    ExportReceipt,
    ExportRequest,
    PresentationUnitProfileId,
)
from pp_fx_architecture_examples.application.contracts.operations import (
    AlignedDatasets,
    AlignmentReport,
    ContextExpansionRequest,
    ContextExpansionResult,
    ContextRequirementSpec,
    DatasetAlignmentRequest,
    NormalizationReport,
    NormalizationRequest,
    NormalizationResult,
    PluginExecutionResult,
    PreparedNodeInput,
    ProducedTableArtifact,
    RoleTable,
    ScopeResolutionRequest,
    ScopeResolutionResult,
)
from pp_fx_architecture_examples.application.contracts.plans import (
    CatalogLock,
    CompiledGraph,
    CompiledNodeSpec,
    CompiledPlan,
    GraphNodeSpec,
    ProcessingTarget,
    ContentHash,
    FunctionPackLock,
)
from pp_fx_architecture_examples.application.contracts.policies import (
    AlignmentPolicy,
    BoundaryPolicy,
    NormalizationPolicy,
    OutOfRangeMode,
)
from pp_fx_architecture_examples.application.contracts.providers import (
    CatalogRequest,
    CatalogSnapshot,
    FunctionPackRequest,
    FunctionPackSnapshot,
    PlanDefinition,
    PlanReference,
)
from pp_fx_architecture_examples.application.contracts.reports import (
    ExecutionInstanceStatusRecord,
    ExecutionReport,
    ReportStatus,
)
from pp_fx_architecture_examples.application.contracts.tables import TableHandle
from pp_fx_architecture_examples.application.ports.exports import ReportExporter
from pp_fx_architecture_examples.application.ports.gateways import (
    CompiledPlanRepository,
    DatasetGateway,
    ParameterGateway,
)
from pp_fx_architecture_examples.application.ports.processing import (
    ContextExpander,
    DatasetAligner,
    DatasetNormalizer,
    ScopeResolver,
)
from pp_fx_architecture_examples.application.ports.providers import (
    CatalogProvider,
    FunctionPackProvider,
    PlanProvider,
)
from pp_fx_architecture_examples.application.ports.plugins import PluginExecutionPort
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
    CatalogId,
    ChannelId,
    CompiledPlanId,
    DatasetReference,
    DatasetRole,
    ExecutionInstanceId,
    FunctionPackId,
    IngestionProfileReference,
    ParameterSetReference,
    PlanId,
    ProcessingTargetId,
    ScopeId,
)
from pp_fx_architecture_examples.domain.results import NodeStatus
from pp_fx_architecture_examples.domain.scopes import (
    BoundaryMode,
    CoordinateAxis,
    RequestedScope,
    ResolvedScope,
)
from pp_fx_architecture_examples.domain.units import Quantity, QuantityKind, Unit

PORTS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/application/ports"
)
FAKES_FILE = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/adapters/fakes.py"
)
DISTANCE = QuantityKind("distance")
METRE = Unit(key="si.metre", symbol="m", quantity_kind=DISTANCE)
REQUESTED_SCOPE = RequestedScope(
    id=ScopeId("scope.corner"),
    axis=CoordinateAxis(ChannelId("lap.distance"), DISTANCE, METRE),
    start=Quantity(Decimal("500"), METRE),
    end=Quantity(Decimal("700"), METRE),
)
RESOLVED_SCOPE = ResolvedScope(
    requested=REQUESTED_SCOPE,
    effective_start=REQUESTED_SCOPE.start,
    effective_end=REQUESTED_SCOPE.end,
    boundary_mode=BoundaryMode.EXACT,
)
BINDING = DatasetBinding(
    role=DatasetRole("primary"),
    dataset=DatasetReference("result-123"),
    ingestion_profile=IngestionProfileReference("acme.mat_v4"),
)
LOADED = LoadedDataset(
    binding=BINDING,
    table=TableHandle("request-1/raw-primary"),
    fingerprint=DatasetFingerprint("sha256:" + "a" * 64),
)
PACK_LOCK = FunctionPackLock(
    id=FunctionPackId("pack.standard"),
    version="1.0.0",
    distribution_hash=ContentHash("sha256", "a" * 64),
    declaration_hash=ContentHash("sha256", "b" * 64),
)
NODE = CompiledNodeSpec(
    id=CalculationNodeId("standard.speed.maximum"),
    pack=PACK_LOCK,
    consumes=(ArtifactId("raw.vehicle.speed"),),
    produces=(ArtifactId("result.speed.maximum"),),
)
PLAN = CompiledPlan(
    id=CompiledPlanId("plan.example"),
    plugin_api_version="1.0",
    unit_registry_version="2026.1",
    function_packs=(PACK_LOCK,),
    catalogs=(
        CatalogLock(
            id=CatalogId("catalog.standard"),
            version="2026.1",
            content_hash=ContentHash("sha256", "c" * 64),
        ),
    ),
    graph=CompiledGraph(
        sources=(
            ArtifactSource(
                ArtifactOutput(
                    ArtifactId("raw.vehicle.speed"),
                    ArtifactKind.RAW_CHANNEL,
                )
            ),
        ),
        nodes=(
            GraphNodeSpec(
                specification=NODE,
                inputs=(
                    ArtifactInput(
                        ArtifactId("raw.vehicle.speed"),
                        ArtifactKind.RAW_CHANNEL,
                        ScopeEdgeMode.SAME_SCOPE,
                    ),
                ),
                outputs=(
                    ArtifactOutput(
                        ArtifactId("result.speed.maximum"),
                        ArtifactKind.SCALAR_KPI,
                    ),
                ),
            ),
        ),
        edges=(),
        targets=(
            ProcessingTarget(
                id=ProcessingTargetId("target.speed_max"),
                exports=(ArtifactId("result.speed.maximum"),),
            ),
        ),
        topological_order=(NODE.id,),
    ),
)


def test_gateway_and_repository_fakes_satisfy_protocols() -> None:
    parameter_binding = ParameterBinding(ParameterSetReference("setup-42"))
    parameter_set = ParameterSet(
        reference=parameter_binding.parameter_set,
        values=(),
    )
    dataset_gateway = FakeDatasetGateway(datasets=(LOADED,))
    parameter_gateway = FakeParameterGateway(parameter_sets=(parameter_set,))
    repository = FakeCompiledPlanRepository(plans=(PLAN,))

    assert isinstance(dataset_gateway, DatasetGateway)
    assert isinstance(parameter_gateway, ParameterGateway)
    assert isinstance(repository, CompiledPlanRepository)
    assert dataset_gateway.load(BINDING) == LOADED
    assert parameter_gateway.load(parameter_binding) == parameter_set
    assert repository.get(PLAN.id) == PLAN


def test_processing_fakes_satisfy_focused_protocols() -> None:
    scope_request = ScopeResolutionRequest(
        dataset=LOADED,
        scope=REQUESTED_SCOPE,
        boundary_policy=BoundaryPolicy(BoundaryMode.EXACT, OutOfRangeMode.REJECT),
    )
    scope_result = ScopeResolutionResult(dataset=LOADED, scope=RESOLVED_SCOPE)
    normalization_request = NormalizationRequest(
        dataset=LOADED,
        policy=NormalizationPolicy.STRICT,
    )
    normalization_result = NormalizationResult(
        dataset=LOADED,
        report=NormalizationReport(changes=()),
    )
    context_request = ContextExpansionRequest(
        dataset=LOADED,
        scope=RESOLVED_SCOPE,
        requirement=ContextRequirementSpec(before_samples=2, after_samples=2),
    )
    context_result = ContextExpansionResult(
        dataset=LOADED,
        target_scope=RESOLVED_SCOPE,
        available_before_samples=2,
        available_after_samples=2,
    )
    alignment_request = DatasetAlignmentRequest(
        primary=context_result,
        comparisons=(),
        policy=AlignmentPolicy.EXACT,
    )
    alignment_result = AlignedDatasets(
        values=(RoleTable(DatasetRole("primary"), LOADED.table),),
        report=AlignmentReport(changes=()),
    )

    resolver = FakeScopeResolver(scope_result)
    normalizer = FakeDatasetNormalizer(normalization_result)
    expander = FakeContextExpander(context_result)
    aligner = FakeDatasetAligner(alignment_result)

    assert isinstance(resolver, ScopeResolver)
    assert isinstance(normalizer, DatasetNormalizer)
    assert isinstance(expander, ContextExpander)
    assert isinstance(aligner, DatasetAligner)
    assert resolver.resolve(scope_request) == scope_result
    assert normalizer.normalize(normalization_request) == normalization_result
    assert expander.expand(context_request) == context_result
    assert aligner.align(alignment_request) == alignment_result


def test_plugin_executor_fake_satisfies_port_without_a_callable_registry() -> None:
    prepared = PreparedNodeInput(
        datasets=(RoleTable(DatasetRole("primary"), LOADED.table),),
        parameters=ParameterSet(ParameterSetReference("setup-42"), ()),
        scope=RESOLVED_SCOPE,
    )
    execution = PluginExecutionResult(
        node_id=NODE.id,
        scalar_results=(),
        table_artifacts=(
            ProducedTableArtifact(
                id=ArtifactId("derived.vehicle.speed"),
                table=TableHandle("request-1/derived-speed"),
            ),
        ),
    )
    executor = FakePluginExecutor(result=execution)

    assert isinstance(executor, PluginExecutionPort)
    assert executor.execute(NODE, prepared) == execution
    assert not any(callable(value) for value in vars(executor).values())


def test_provider_fakes_return_framework_neutral_snapshots() -> None:
    plan_reference = PlanReference(PlanId("plan.source"), ">=1,<2")
    plan_definition = PlanDefinition(
        reference=plan_reference,
        function_packs=(FunctionPackRequest(PACK_LOCK.id, ">=1,<2"),),
        catalogs=(CatalogRequest(CatalogId("catalog.standard"), ">=2026,<2027"),),
        targets=PLAN.targets,
    )
    catalog_request = plan_definition.catalogs[0]
    catalog_snapshot = CatalogSnapshot(PLAN.catalogs[0])
    pack_request = plan_definition.function_packs[0]
    pack_snapshot = FunctionPackSnapshot(
        lock=PACK_LOCK,
        node_ids=(NODE.id,),
    )

    plan_provider = FakePlanProvider(definitions=(plan_definition,))
    catalog_provider = FakeCatalogProvider(snapshots=(catalog_snapshot,))
    pack_provider = FakeFunctionPackProvider(snapshots=(pack_snapshot,))

    assert isinstance(plan_provider, PlanProvider)
    assert isinstance(catalog_provider, CatalogProvider)
    assert isinstance(pack_provider, FunctionPackProvider)
    assert plan_provider.get(plan_reference) == plan_definition
    assert catalog_provider.get(catalog_request) == catalog_snapshot
    assert pack_provider.get(pack_request) == pack_snapshot


def test_report_exporter_fake_receives_report_through_export_contract() -> None:
    failure = FailureDetail(
        FailureCategory.NODE,
        "PLUGIN_EXCEPTION",
        "The plugin raised an expected node-level failure.",
    )
    report = ExecutionReport(
        compiled_plan=PLAN.id,
        datasets=DatasetBindings((BINDING,)),
        requested_scope=REQUESTED_SCOPE,
        resolved_scope=RESOLVED_SCOPE,
        status=ReportStatus.FAILED,
        results=(),
        instances=(
            ExecutionInstanceStatusRecord(
                execution_instance=ExecutionInstanceId("instance.speed_max"),
                node_id=NODE.id,
                scope=REQUESTED_SCOPE.id,
                occurrence=None,
                status=NodeStatus.FAILED,
                failure=failure,
            ),
        ),
    )
    destination = ExportDestination("memory:report-1")
    request = ExportRequest(
        report=report,
        format=ExportFormat.JSON,
        presentation_units=PresentationUnitProfileId("units.metric"),
        destination=destination,
    )
    receipt = ExportReceipt(destination=destination, artifact_count=1)
    exporter = FakeReportExporter(receipt)

    assert isinstance(exporter, ReportExporter)
    assert exporter.export(request) == receipt


def test_parameter_gateway_returns_application_contract_parameter_set() -> None:
    return_type = get_type_hints(inspect.getattr_static(ParameterGateway, "load"))["return"]

    assert return_type is ParameterSet
    assert ParameterSet.__module__.endswith("application.contracts.datasets")


def test_ports_import_only_standard_library_and_application_contracts() -> None:
    violations: list[str] = []

    for source_file in sorted(PORTS_ROOT.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for imported in (alias.name for alias in node.names):
                    if imported.partition(".")[0] not in sys.stdlib_module_names:
                        violations.append(f"{source_file.name}:{node.lineno}:{imported}")
                continue
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            standard_library = node.level == 0 and (
                node.module == "__future__"
                or node.module.partition(".")[0] in sys.stdlib_module_names
            )
            contract_import = node.level == 2 and (
                node.module == "contracts" or node.module.startswith("contracts.")
            )
            if not standard_library and not contract_import:
                violations.append(f"{source_file.name}:{node.lineno}:{node.module}")

    assert violations == []


def test_fakes_do_not_choose_framework_or_driver_technology() -> None:
    tree = ast.parse(FAKES_FILE.read_text(encoding="utf-8"), FAKES_FILE.name)
    imported = {
        name
        for node in ast.walk(tree)
        for name in imported_names(node)
    }
    forbidden = {"pandas", "pathlib", "argparse", "importlib", "entry_points"}

    assert not any(part in forbidden for name in imported for part in name.split("."))


def imported_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()
