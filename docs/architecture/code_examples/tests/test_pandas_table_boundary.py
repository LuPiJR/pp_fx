from __future__ import annotations

import ast
import sys
from dataclasses import fields
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from pp_fx_architecture_examples.adapters.pandas_tables.gateway import (
    InMemoryPandasDatasetGateway,
    PandasDatasetSource,
)
from pp_fx_architecture_examples.adapters.pandas_tables.plugins import (
    PandasNodeInput,
    PandasPluginExecutor,
)
from pp_fx_architecture_examples.adapters.pandas_tables.processing import (
    PandasRoleTable,
    WorkspaceDatasetAligner,
    WorkspaceScopeResolver,
)
from pp_fx_architecture_examples.adapters.pandas_tables.workspace import (
    PandasTableWorkspace,
    TableWorkspace,
    UnknownTableHandle,
    WorkspaceDisposedError,
)
from pp_fx_architecture_examples.application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
    DatasetFingerprint,
    LoadedDataset,
    ParameterSet,
)
from pp_fx_architecture_examples.application.contracts.operations import (
    AlignmentReport,
    ContextExpansionResult,
    DatasetAlignmentRequest,
    PreparedNodeInput,
    RoleTable,
    ScopeResolutionRequest,
)
from pp_fx_architecture_examples.application.contracts.plans import (
    CompiledNodeSpec,
    ContentHash,
    FunctionPackLock,
)
from pp_fx_architecture_examples.application.contracts.policies import (
    AlignmentPolicy,
    BoundaryPolicy,
    OutOfRangeMode,
)
from pp_fx_architecture_examples.application.contracts.reports import (
    ExecutionCompleted,
    ExecutionInstanceStatusRecord,
    ExecutionReport,
    ProcessOutcome,
    ReportStatus,
    RequestRejected,
)
from pp_fx_architecture_examples.application.contracts.tables import TableHandle
from pp_fx_architecture_examples.application.ports.gateways import DatasetGateway
from pp_fx_architecture_examples.application.ports.plugins import PluginExecutionPort
from pp_fx_architecture_examples.application.ports.processing import (
    DatasetAligner,
    ScopeResolver,
)
from pp_fx_architecture_examples.domain.failures import FailureCategory, FailureDetail
from pp_fx_architecture_examples.domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    ChannelId,
    CompiledPlanId,
    DatasetReference,
    DatasetRole,
    ExecutionInstanceId,
    FunctionPackId,
    IngestionProfileReference,
    ParameterSetReference,
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

APPLICATION_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/application"
)
PANDAS_ADAPTER_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/adapters/pandas_tables"
)
DISTANCE = QuantityKind("distance")
METRE = Unit("si.metre", "m", DISTANCE)
REQUESTED_SCOPE = RequestedScope(
    id=ScopeId("scope.selection"),
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
PRIMARY_BINDING = DatasetBinding(
    role=DatasetRole("primary"),
    dataset=DatasetReference("dataset-primary"),
    ingestion_profile=IngestionProfileReference("example.in_memory_v1"),
)
REFERENCE_BINDING = DatasetBinding(
    role=DatasetRole("reference"),
    dataset=DatasetReference("dataset-reference"),
    ingestion_profile=IngestionProfileReference("example.in_memory_v1"),
)
FINGERPRINT = DatasetFingerprint("sha256:" + "a" * 64)
PACK_LOCK = FunctionPackLock(
    id=FunctionPackId("pack.example"),
    version="1.0.0",
    distribution_hash=ContentHash("sha256", "b" * 64),
    declaration_hash=ContentHash("sha256", "c" * 64),
)
NODE = CompiledNodeSpec(
    id=CalculationNodeId("example.derived.speed"),
    pack=PACK_LOCK,
    consumes=(ArtifactId("raw.vehicle.speed"),),
    produces=(ArtifactId("derived.vehicle.speed"),),
)
SUCCESS_OUTCOME: ProcessOutcome = ExecutionCompleted(
    ExecutionReport(
        compiled_plan=CompiledPlanId("plan.example"),
        datasets=DatasetBindings((PRIMARY_BINDING,)),
        requested_scope=REQUESTED_SCOPE,
        resolved_scope=RESOLVED_SCOPE,
        status=ReportStatus.SUCCESS,
        results=(),
        instances=(
            ExecutionInstanceStatusRecord(
                execution_instance=ExecutionInstanceId("instance.example"),
                node_id=NODE.id,
                scope=REQUESTED_SCOPE.id,
                occurrence=None,
                status=NodeStatus.SUCCEEDED,
            ),
        ),
    )
)
REJECTED_OUTCOME: ProcessOutcome = RequestRejected(
    (
        FailureDetail(
            category=FailureCategory.REQUEST,
            code="DATASET_UNAVAILABLE",
            message="The requested dataset is unavailable.",
        ),
    )
)


def test_application_facing_values_expose_no_pandas_type() -> None:
    pandas_imports: list[str] = []

    for source_file in sorted(APPLICATION_ROOT.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = (node.module,)
            else:
                imported = ()
            if any(name == "pandas" or name.startswith("pandas.") for name in imported):
                pandas_imports.append(f"{source_file.name}:{node.lineno}")

    assert pandas_imports == []
    assert tuple(field.name for field in fields(TableHandle)) == ("token",)


def test_pandas_adapters_depend_only_on_pandas_and_inward_values() -> None:
    violations: list[str] = []

    for source_file in sorted(PANDAS_ADAPTER_ROOT.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for imported in (alias.name for alias in node.names):
                    root = imported.partition(".")[0]
                    if root != "pandas" and root not in sys.stdlib_module_names:
                        violations.append(f"{source_file.name}:{node.lineno}:{imported}")
                continue
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            standard_library = node.level == 0 and (
                node.module == "__future__"
                or node.module.partition(".")[0] in sys.stdlib_module_names
            )
            sibling = node.level == 1
            inward = node.level == 3 and node.module.startswith(
                ("application.contracts.", "domain.")
            )
            if not standard_library and not sibling and not inward:
                violations.append(f"{source_file.name}:{node.lineno}:{node.module}")

    assert violations == []


def test_handles_resolve_only_inside_the_own_live_workspace() -> None:
    first: TableWorkspace = PandasTableWorkspace()
    second: TableWorkspace = PandasTableWorkspace()
    frame = pd.DataFrame({"speed": [10.0, 11.0]})

    handle = first.store(frame, label="primary")

    assert first.resolve(handle) is frame
    with pytest.raises(UnknownTableHandle):
        second.resolve(handle)

    first.dispose()
    with pytest.raises(WorkspaceDisposedError):
        first.resolve(handle)


def test_dataset_gateway_returns_metadata_and_an_opaque_handle() -> None:
    workspace = PandasTableWorkspace()
    source_frame = pd.DataFrame(
        {"lap.distance": [500.0, 600.0, 700.0], "vehicle.speed": [40.0, 42.0, 41.0]}
    )
    gateway = InMemoryPandasDatasetGateway(
        workspace,
        sources=(
            PandasDatasetSource(PRIMARY_BINDING, source_frame, FINGERPRINT),
        ),
    )

    loaded = gateway.load(PRIMARY_BINDING)

    assert isinstance(gateway, DatasetGateway)
    assert loaded.binding == PRIMARY_BINDING
    assert loaded.fingerprint == FINGERPRINT
    assert isinstance(loaded.table, TableHandle)
    assert workspace.resolve(loaded.table) is not source_frame
    pd.testing.assert_frame_equal(workspace.resolve(loaded.table), source_frame)


def test_scope_and_alignment_adapters_resolve_handles_internally() -> None:
    workspace = PandasTableWorkspace()
    primary = load_dataset(
        workspace,
        PRIMARY_BINDING,
        pd.DataFrame({"lap.distance": [500.0, 600.0, 700.0]}),
    )
    reference = load_dataset(
        workspace,
        REFERENCE_BINDING,
        pd.DataFrame({"lap.distance": [500.0, 610.0, 700.0]}),
    )
    scope_kernel = RecordingScopeKernel()
    scope_adapter = WorkspaceScopeResolver(workspace, scope_kernel)
    scope_request = ScopeResolutionRequest(
        dataset=primary,
        scope=REQUESTED_SCOPE,
        boundary_policy=BoundaryPolicy(BoundaryMode.EXACT, OutOfRangeMode.REJECT),
    )

    scoped = scope_adapter.resolve(scope_request)

    assert isinstance(scope_adapter, ScopeResolver)
    assert scope_kernel.received is workspace.resolve(primary.table)
    assert scoped.scope == RESOLVED_SCOPE
    assert scoped.dataset.table != primary.table

    alignment_kernel = RecordingAlignmentKernel()
    aligner = WorkspaceDatasetAligner(workspace, alignment_kernel)
    alignment_request = DatasetAlignmentRequest(
        primary=ContextExpansionResult(
            dataset=scoped.dataset,
            target_scope=RESOLVED_SCOPE,
            available_before_samples=0,
            available_after_samples=0,
        ),
        comparisons=(reference,),
        policy=AlignmentPolicy.EXACT,
    )

    aligned = aligner.align(alignment_request)

    assert isinstance(aligner, DatasetAligner)
    assert alignment_kernel.primary is workspace.resolve(scoped.dataset.table)
    assert alignment_kernel.reference is workspace.resolve(reference.table)
    assert tuple(item.role for item in aligned.values) == (
        DatasetRole("primary"),
        DatasetRole("reference"),
    )
    assert all(isinstance(item.table, TableHandle) for item in aligned.values)


def test_plugin_invocation_receives_only_node_local_frame_copies() -> None:
    workspace = PandasTableWorkspace()
    canonical = pd.DataFrame({"vehicle.speed": [40.0, 42.0]}, index=[10, 11])
    canonical_handle = workspace.store(canonical, label="aligned-primary")
    prepared = PreparedNodeInput(
        datasets=(RoleTable(DatasetRole("primary"), canonical_handle),),
        parameters=ParameterSet(ParameterSetReference("parameters.empty"), ()),
        scope=RESOLVED_SCOPE,
    )
    invoker = MutatingRecordingInvoker()
    executor = PandasPluginExecutor(workspace, invoker)

    result = executor.execute(NODE, prepared)

    assert isinstance(executor, PluginExecutionPort)
    assert invoker.received is not canonical
    assert canonical.loc[10, "vehicle.speed"] == 40.0
    assert result.node_id == NODE.id
    assert result.scalar_results == ()
    assert result.table_artifacts[0].id == NODE.produces[0]
    produced = workspace.resolve(result.table_artifacts[0].table)
    assert tuple(produced["derived.speed"]) == (999.0, 42.0)


@pytest.mark.parametrize("outcome", [SUCCESS_OUTCOME, REJECTED_OUTCOME])
def test_workspace_context_disposes_after_normal_completion(
    outcome: ProcessOutcome,
) -> None:
    workspace = PandasTableWorkspace()

    def complete_request() -> ProcessOutcome:
        with workspace:
            workspace.store(pd.DataFrame({"value": [1]}), label="request-table")
            return outcome

    assert complete_request() is outcome
    assert workspace.disposed is True


def test_workspace_context_disposes_after_raised_system_failure() -> None:
    workspace = PandasTableWorkspace()

    with pytest.raises(RuntimeError, match="system failure"):
        with workspace:
            workspace.store(pd.DataFrame({"value": [1]}), label="request-table")
            raise RuntimeError("system failure")

    assert workspace.disposed is True


def load_dataset(
    workspace: PandasTableWorkspace,
    binding: DatasetBinding,
    frame: pd.DataFrame,
) -> LoadedDataset:
    gateway = InMemoryPandasDatasetGateway(
        workspace,
        sources=(PandasDatasetSource(binding, frame, FINGERPRINT),),
    )
    return gateway.load(binding)


class RecordingScopeKernel:
    def __init__(self) -> None:
        self.received: pd.DataFrame | None = None

    def resolve(
        self,
        table: pd.DataFrame,
        request: ScopeResolutionRequest,
    ) -> tuple[pd.DataFrame, ResolvedScope]:
        self.received = table
        return table.copy(deep=True), RESOLVED_SCOPE


class RecordingAlignmentKernel:
    def __init__(self) -> None:
        self.primary: pd.DataFrame | None = None
        self.reference: pd.DataFrame | None = None

    def align(
        self,
        primary: pd.DataFrame,
        comparisons: tuple[PandasRoleTable, ...],
        request: DatasetAlignmentRequest,
    ) -> tuple[tuple[PandasRoleTable, ...], AlignmentReport]:
        self.primary = primary
        self.reference = comparisons[0].table
        return (
            (
                PandasRoleTable(DatasetRole("primary"), primary.copy(deep=True)),
                PandasRoleTable(
                    DatasetRole("reference"),
                    comparisons[0].table.copy(deep=True),
                ),
            ),
            AlignmentReport(changes=()),
        )


class MutatingRecordingInvoker:
    def __init__(self) -> None:
        self.received: pd.DataFrame | None = None

    def invoke(self, node: CompiledNodeSpec, data: PandasNodeInput) -> pd.DataFrame:
        self.received = data.frame
        data.frame.loc[10, "vehicle.speed"] = 999.0
        return data.frame.rename(columns={"vehicle.speed": "derived.speed"})
