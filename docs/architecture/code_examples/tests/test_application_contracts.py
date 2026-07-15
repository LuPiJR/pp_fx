from __future__ import annotations

import ast
import json
import sys
from dataclasses import FrozenInstanceError, asdict, fields
from decimal import Decimal
from pathlib import Path

import pytest

from pp_fx_architecture_examples.application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
    ParameterBinding,
    ParameterEntry,
    ParameterSet,
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
    NodeConfigurationEntry,
)
from pp_fx_architecture_examples.application.contracts.policies import (
    AlignmentPolicy,
    BoundaryPolicy,
    NormalizationPolicy,
    OutOfRangeMode,
)
from pp_fx_architecture_examples.application.contracts.reports import (
    ExecutionCompleted,
    ExecutionInstanceStatusRecord,
    ExecutionReport,
    ProcessOutcome,
    ReportStatus,
    RequestRejected,
    ResultRecord,
)
from pp_fx_architecture_examples.application.contracts.requests import ProcessingRequest
from pp_fx_architecture_examples.application.contracts.tables import TableHandle
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
    ParameterId,
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

CONTRACTS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/application/contracts"
)
DISTANCE = QuantityKind("distance")
METRE = Unit(key="si.metre", symbol="m", quantity_kind=DISTANCE)
SCOPE = RequestedScope(
    id=ScopeId("scope.corner"),
    axis=CoordinateAxis(
        id=ChannelId("lap.distance"),
        quantity_kind=DISTANCE,
        canonical_unit=METRE,
    ),
    start=Quantity(Decimal("500"), METRE),
    end=Quantity(Decimal("700"), METRE),
)
PRIMARY = DatasetBinding(
    role=DatasetRole("primary"),
    dataset=DatasetReference("result-123"),
    ingestion_profile=IngestionProfileReference("acme.mat_v4"),
)
PARAMETER_BINDING = ParameterBinding(
    parameter_set=ParameterSetReference("setup-42"),
    ingestion_profile=IngestionProfileReference("acme.parameters_v2"),
)


def test_processing_request_contains_only_transport_neutral_typed_values() -> None:
    request = make_request()

    assert request.datasets.values == (PRIMARY,)
    assert request.parameters == PARAMETER_BINDING
    assert request.targets == (ProcessingTargetId("target.speed_max"),)
    assert "presentation" not in {field.name for field in fields(ProcessingRequest)}
    assert "unit_profile" not in {field.name for field in fields(ProcessingRequest)}
    assert not contains_forbidden_transport_value(request)

    with pytest.raises(FrozenInstanceError):
        request.targets = ()  # type: ignore[misc]


def test_dataset_bindings_require_one_primary_role_and_unique_roles() -> None:
    reference = DatasetBinding(
        role=DatasetRole("reference"),
        dataset=DatasetReference("reference-42"),
        ingestion_profile=IngestionProfileReference("acme.mat_v4"),
    )
    bindings = DatasetBindings(values=(PRIMARY, reference))

    assert bindings.primary is PRIMARY

    with pytest.raises(ValueError, match="exactly one primary"):
        DatasetBindings(values=(reference,))
    with pytest.raises(ValueError, match="unique"):
        DatasetBindings(values=(PRIMARY, PRIMARY))


def test_parameter_set_is_application_owned_but_uses_domain_values() -> None:
    wheelbase = ParameterEntry(
        id=ParameterId("vehicle.geometry.wheelbase"),
        value=Quantity(Decimal("3.1"), METRE),
    )
    parameters = ParameterSet(
        reference=ParameterSetReference("setup-42"),
        values=(wheelbase,),
    )

    assert isinstance(parameters.values[0].id, ParameterId)
    assert isinstance(parameters.values[0].value, Quantity)

    with pytest.raises(ValueError, match="unique"):
        ParameterSet(
            reference=ParameterSetReference("setup-42"),
            values=(wheelbase, wheelbase),
        )


def test_compiled_plan_is_serializable_and_contains_no_callable() -> None:
    plan = make_compiled_plan()
    payload = asdict(plan)

    assert json.loads(json.dumps(payload))["id"]["value"] == "plan.example"
    assert not contains_callable(plan)
    assert plan.nodes[0].configuration == (
        NodeConfigurationEntry(key="threshold_bar", value=90.0),
    )
    assert plan.graph.topological_order == (plan.nodes[0].id,)


def test_request_rejection_has_no_execution_report() -> None:
    rejection = RequestRejected(
        failures=(
            FailureDetail(
                category=FailureCategory.REQUEST,
                code="PRIMARY_DATASET_UNAVAILABLE",
                message="The primary dataset is unavailable.",
            ),
        )
    )
    outcome: ProcessOutcome = rejection

    assert isinstance(outcome, RequestRejected)
    assert not hasattr(outcome, "report")

    with pytest.raises(ValueError, match="request-level"):
        RequestRejected(
            failures=(
                FailureDetail(
                    category=FailureCategory.NODE,
                    code="MISSING_CHANNEL",
                    message="A required channel is unavailable.",
                ),
            )
        )


def test_execution_completed_contains_authoritative_typed_report() -> None:
    plan = make_compiled_plan()
    node_id = CalculationNodeId("standard.speed.maximum")
    instance_id = ExecutionInstanceId("instance.speed_max")
    provenance = ResultProvenance(
        node_id=node_id,
        input_artifacts=(ArtifactId("raw.vehicle.speed"),),
        calculation_unit=METRE,
    )
    result = ResultRecord(
        node_id=node_id,
        execution_instance=instance_id,
        target_id=ProcessingTargetId("target.speed_max"),
        dataset_role=DatasetRole("primary"),
        scope=ScopeId("scope.corner"),
        occurrence=None,
        scope_ancestry=(ScopeId("scope.corner"),),
        artifact=ArtifactResult(
            artifact_id=ArtifactId("result.speed.maximum"),
            status=NodeStatus.SUCCEEDED,
            value=Quantity(Decimal("42"), METRE),
            provenance=provenance,
        ),
    )
    instance = ExecutionInstanceStatusRecord(
        execution_instance=instance_id,
        node_id=node_id,
        scope=ScopeId("scope.corner"),
        occurrence=None,
        status=NodeStatus.SUCCEEDED,
    )
    report = ExecutionReport(
        compiled_plan=plan.id,
        datasets=DatasetBindings(values=(PRIMARY,)),
        requested_scope=SCOPE,
        resolved_scope=ResolvedScope(
            requested=SCOPE,
            effective_start=SCOPE.start,
            effective_end=SCOPE.end,
            boundary_mode=BoundaryMode.EXACT,
        ),
        status=ReportStatus.SUCCESS,
        results=(result,),
        instances=(instance,),
    )
    outcome: ProcessOutcome = ExecutionCompleted(report=report)

    assert isinstance(outcome, ExecutionCompleted)
    assert outcome.report.results == (result,)
    assert outcome.report.instances == (instance,)
    assert outcome.report.status is ReportStatus.SUCCESS


def test_table_handle_is_an_opaque_nominal_value() -> None:
    handle = TableHandle("request-7/table-primary")

    assert handle.token == "request-7/table-primary"
    assert tuple(field.name for field in fields(handle)) == ("token",)
    assert not hasattr(handle, "frame")


def test_contract_modules_depend_only_on_domain_and_sibling_contracts() -> None:
    violations: list[str] = []

    for source_file in sorted(CONTRACTS_ROOT.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for imported in (alias.name for alias in node.names):
                    if imported.partition(".")[0] not in sys.stdlib_module_names:
                        violations.append(
                            f"{source_file.name}:{node.lineno}:{imported}"
                        )
                continue

            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.level == 1:
                continue
            if node.level == 3 and (
                node.module == "domain" or node.module.startswith("domain.")
            ):
                continue
            if node.level == 0 and (
                node.module == "__future__"
                or node.module.partition(".")[0] in sys.stdlib_module_names
            ):
                continue
            violations.append(f"{source_file.name}:{node.lineno}:{node.module}")

    assert violations == []


def make_request() -> ProcessingRequest:
    return ProcessingRequest(
        compiled_plan=CompiledPlanId("plan.example"),
        datasets=DatasetBindings(values=(PRIMARY,)),
        parameters=PARAMETER_BINDING,
        targets=(ProcessingTargetId("target.speed_max"),),
        scope=SCOPE,
        boundary_policy=BoundaryPolicy(
            mode=BoundaryMode.EXACT,
            out_of_range=OutOfRangeMode.REJECT,
        ),
        alignment_policy=AlignmentPolicy.EXACT,
        normalization_policy=NormalizationPolicy.STRICT,
    )


def make_compiled_plan() -> CompiledPlan:
    digest_a = ContentHash(algorithm="sha256", digest="a" * 64)
    digest_b = ContentHash(algorithm="sha256", digest="b" * 64)
    pack = FunctionPackLock(
        id=FunctionPackId("pack.standard"),
        version="1.0.0",
        distribution_hash=digest_a,
        declaration_hash=digest_b,
    )
    node = CompiledNodeSpec(
        id=CalculationNodeId("standard.speed.maximum"),
        pack=pack,
        consumes=(ArtifactId("raw.vehicle.speed"),),
        produces=(ArtifactId("result.speed.maximum"),),
        configuration=(
            NodeConfigurationEntry(key="threshold_bar", value=90.0),
        ),
    )
    return CompiledPlan(
        id=CompiledPlanId("plan.example"),
        plugin_api_version="1.0",
        unit_registry_version="2026.1",
        function_packs=(pack,),
        catalogs=(
            CatalogLock(
                id=CatalogId("catalog.standard"),
                version="2026.1",
                content_hash=digest_a,
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
                    specification=node,
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
            topological_order=(node.id,),
        ),
    )


def contains_forbidden_transport_value(value: object) -> bool:
    value_module = type(value).__module__
    if isinstance(value, (dict, Path)):
        return True
    if value_module.startswith(("pandas", "pp_fx_architecture_examples.plugin_api")):
        return True
    if hasattr(value, "__dataclass_fields__"):
        return any(
            contains_forbidden_transport_value(getattr(value, field.name))
            for field in fields(value)  # type: ignore[arg-type]
        )
    if isinstance(value, tuple):
        return any(contains_forbidden_transport_value(item) for item in value)
    return False


def contains_callable(value: object) -> bool:
    if callable(value):
        return True
    if hasattr(value, "__dataclass_fields__"):
        return any(
            contains_callable(getattr(value, field.name))
            for field in fields(value)  # type: ignore[arg-type]
        )
    if isinstance(value, tuple):
        return any(contains_callable(item) for item in value)
    return False
