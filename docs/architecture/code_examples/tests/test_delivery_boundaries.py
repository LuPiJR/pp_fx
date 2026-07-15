from __future__ import annotations

import ast
from dataclasses import fields, replace
from decimal import Decimal
from pathlib import Path

import pytest

from pp_fx_architecture_examples.application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
)
from pp_fx_architecture_examples.application.contracts.exports import (
    ExportDestination,
    ExportFailed,
    ExportFormat,
    ExportOutcome,
    ExportReceipt,
    ExportRequest,
    PresentationUnitProfileId,
)
from pp_fx_architecture_examples.application.contracts.reports import (
    ExecutionCompleted,
    ExecutionInstanceStatusRecord,
    ExecutionReport,
    ProcessOutcome,
    ReportStatus,
    RequestRejected,
)
from pp_fx_architecture_examples.application.contracts.requests import ProcessingRequest
from pp_fx_architecture_examples.application.ports.exports import ReportExporter
from pp_fx_architecture_examples.application.ports.use_cases import ExportReport, ProcessDataset
from pp_fx_architecture_examples.application.services.export_report import (
    ExportReportService,
)
from pp_fx_architecture_examples.delivery.outcome_mapping import (
    CliExitCode,
    GrpcStatusCode,
    map_export_outcome_to_cli,
    map_export_outcome_to_grpc,
    map_process_outcome_to_cli,
    map_process_outcome_to_grpc,
    map_system_failure_to_cli,
    map_system_failure_to_grpc,
)
from pp_fx_architecture_examples.delivery.python_facade import PythonProcessingFacade
from pp_fx_architecture_examples.delivery.request_dtos import (
    JsonBoundaryPolicyV1,
    JsonDatasetBindingV1,
    JsonParameterBindingV1,
    JsonProcessRequestV1,
    JsonQuantityV1,
    JsonScopeV1,
    PythonDatasetInput,
    PythonParameterInput,
    PythonProcessInput,
    PythonScopeInput,
)
from pp_fx_architecture_examples.delivery.request_mapping import (
    DeliveryMappingError,
    FutureGrpcRequestMapper,
    JsonRequestMapperV1,
    PythonRequestBuilder,
)
from pp_fx_architecture_examples.domain.failures import FailureCategory, FailureDetail
from pp_fx_architecture_examples.domain.identifiers import (
    CalculationNodeId,
    ChannelId,
    CompiledPlanId,
    DatasetReference,
    DatasetRole,
    ExecutionInstanceId,
    IngestionProfileReference,
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

DELIVERY_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/delivery"
)
DISTANCE = QuantityKind("distance")
METRE = Unit("si.metre", "m", DISTANCE)
AXIS = CoordinateAxis(ChannelId("lap.distance"), DISTANCE, METRE)


class StaticRequestValueCatalog:
    def resolve_axis(self, reference: str) -> CoordinateAxis | None:
        return AXIS if reference == AXIS.id.value else None

    def resolve_unit(self, reference: str) -> Unit | None:
        return METRE if reference in {METRE.key, METRE.symbol} else None


CATALOG = StaticRequestValueCatalog()
PYTHON_INPUT = PythonProcessInput(
    compiled_plan="plan.example",
    datasets=(
        PythonDatasetInput(
            role="primary",
            reference="dataset-primary",
            ingestion_profile="example.in_memory_v1",
        ),
    ),
    parameters=PythonParameterInput(reference="setup-42"),
    targets=("target.analysis",),
    scope=PythonScopeInput(
        id="scope.selection",
        axis="lap.distance",
        start=Decimal("500"),
        end=Decimal("700"),
        unit="m",
    ),
    boundary_mode="exact",
    out_of_range="reject",
    alignment="exact",
    normalization="strict",
)
JSON_INPUT = JsonProcessRequestV1(
    schema_version="pp-fx.process-request/v1",
    compiled_plan="plan.example",
    datasets=(
        JsonDatasetBindingV1(
            role="primary",
            reference="dataset-primary",
            ingestion_profile="example.in_memory_v1",
        ),
    ),
    parameters=JsonParameterBindingV1(reference="setup-42"),
    targets=("target.analysis",),
    scope=JsonScopeV1(
        id="scope.selection",
        axis="lap.distance",
        start=JsonQuantityV1("500", "m"),
        end=JsonQuantityV1("700", "m"),
    ),
    boundary_policy=JsonBoundaryPolicyV1("exact", "reject"),
    alignment_policy="exact",
    normalization_policy="strict",
)


def test_python_and_json_inputs_map_to_equal_application_requests() -> None:
    python_request = PythonRequestBuilder(CATALOG).build(PYTHON_INPUT)
    json_request = JsonRequestMapperV1(CATALOG).map(JSON_INPUT)

    assert python_request == json_request
    assert python_request.scope.axis == AXIS
    assert python_request.scope.start == Quantity(Decimal("500"), METRE)


def test_invalid_external_ids_and_units_fail_at_delivery_boundary() -> None:
    invalid_id = PythonProcessInput(
        compiled_plan="INVALID",
        datasets=PYTHON_INPUT.datasets,
        parameters=PYTHON_INPUT.parameters,
        targets=PYTHON_INPUT.targets,
        scope=PYTHON_INPUT.scope,
        boundary_mode=PYTHON_INPUT.boundary_mode,
        out_of_range=PYTHON_INPUT.out_of_range,
        alignment=PYTHON_INPUT.alignment,
        normalization=PYTHON_INPUT.normalization,
    )
    invalid_unit = JsonProcessRequestV1(
        schema_version=JSON_INPUT.schema_version,
        compiled_plan=JSON_INPUT.compiled_plan,
        datasets=JSON_INPUT.datasets,
        parameters=JSON_INPUT.parameters,
        targets=JSON_INPUT.targets,
        scope=JsonScopeV1(
            id=JSON_INPUT.scope.id,
            axis=JSON_INPUT.scope.axis,
            start=JsonQuantityV1("500", "furlong"),
            end=JSON_INPUT.scope.end,
        ),
        boundary_policy=JSON_INPUT.boundary_policy,
        alignment_policy=JSON_INPUT.alignment_policy,
        normalization_policy=JSON_INPUT.normalization_policy,
    )

    with pytest.raises(DeliveryMappingError) as id_error:
        PythonRequestBuilder(CATALOG).build(invalid_id)
    with pytest.raises(DeliveryMappingError) as unit_error:
        JsonRequestMapperV1(CATALOG).map(invalid_unit)

    assert id_error.value.path == "compiled_plan"
    assert id_error.value.code == "INVALID_VALUE"
    assert unit_error.value.path == "scope.start.unit"
    assert unit_error.value.code == "UNKNOWN_UNIT"


def test_json_mapper_rejects_unsupported_schema_version() -> None:
    unsupported = replace(JSON_INPUT, schema_version="pp-fx.process-request/v2")

    with pytest.raises(DeliveryMappingError) as error:
        JsonRequestMapperV1(CATALOG).map(unsupported)

    assert error.value.path == "schema_version"
    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_process_outcomes_and_system_failure_map_distinctly() -> None:
    success = ExecutionCompleted(make_report(ReportStatus.SUCCESS))
    partial = ExecutionCompleted(make_report(ReportStatus.PARTIAL_SUCCESS))
    failed = ExecutionCompleted(make_report(ReportStatus.FAILED))
    rejected = RequestRejected(
        (
            FailureDetail(
                FailureCategory.REQUEST,
                "UNKNOWN_TARGET",
                "The target is not in the compiled plan.",
            ),
        )
    )

    assert map_process_outcome_to_cli(success).exit_code is CliExitCode.SUCCESS
    assert (
        map_process_outcome_to_cli(partial).exit_code
        is CliExitCode.PARTIAL_SUCCESS
    )
    assert (
        map_process_outcome_to_cli(failed).exit_code
        is CliExitCode.PROCESSING_FAILED
    )
    assert (
        map_process_outcome_to_cli(rejected).exit_code
        is CliExitCode.REQUEST_REJECTED
    )
    assert map_process_outcome_to_grpc(success).code is GrpcStatusCode.OK
    partial_grpc = map_process_outcome_to_grpc(partial)
    failed_grpc = map_process_outcome_to_grpc(failed)
    assert partial_grpc.code is GrpcStatusCode.OK
    assert partial_grpc.report_status is ReportStatus.PARTIAL_SUCCESS
    assert failed_grpc.code is GrpcStatusCode.OK
    assert failed_grpc.report_status is ReportStatus.FAILED
    assert (
        map_process_outcome_to_grpc(rejected).code
        is GrpcStatusCode.INVALID_ARGUMENT
    )

    system_error = RuntimeError("workspace disposed unexpectedly")
    assert (
        map_system_failure_to_cli(system_error).exit_code
        is CliExitCode.SYSTEM_FAILURE
    )
    assert (
        map_system_failure_to_grpc(system_error).code
        is GrpcStatusCode.INTERNAL
    )


def test_export_receipt_and_failure_use_a_separate_use_case_and_mapping() -> None:
    request = ExportRequest(
        report=make_report(ReportStatus.SUCCESS),
        format=ExportFormat.JSON,
        presentation_units=PresentationUnitProfileId("units.metric"),
        destination=ExportDestination("memory:report-1"),
    )
    receipt = ExportReceipt(request.destination, artifact_count=1)
    failure = ExportFailed("DESTINATION_UNAVAILABLE", "Destination is unavailable.")

    receipt_exporter = CannedExporter(receipt)
    receipt_service = ExportReportService(receipt_exporter)
    failure_service = ExportReportService(CannedExporter(failure))

    assert isinstance(receipt_service, ExportReport)
    assert isinstance(receipt_exporter, ReportExporter)
    assert receipt_service.execute(request) == receipt
    assert failure_service.execute(request) == failure
    assert map_export_outcome_to_cli(receipt).exit_code is CliExitCode.SUCCESS
    assert (
        map_export_outcome_to_cli(failure).exit_code
        is CliExitCode.EXPORT_FAILURE
    )
    assert map_export_outcome_to_grpc(receipt).code is GrpcStatusCode.OK
    assert (
        map_export_outcome_to_grpc(failure).code
        is GrpcStatusCode.FAILED_PRECONDITION
    )


def test_presentation_units_exist_only_on_export_request() -> None:
    processing_request = PythonRequestBuilder(CATALOG).build(PYTHON_INPUT)

    assert "presentation_units" in {field.name for field in fields(ExportRequest)}
    assert "presentation_units" not in {
        field.name for field in fields(type(processing_request))
    }
    assert "presentation_units" not in {field.name for field in fields(PythonProcessInput)}
    assert "presentation_units" not in {field.name for field in fields(JsonProcessRequestV1)}


def test_python_facade_processes_without_an_exporter() -> None:
    completed = ExecutionCompleted(make_report(ReportStatus.SUCCESS))
    processor = RecordingProcessor(completed)
    facade = PythonProcessingFacade(PythonRequestBuilder(CATALOG), processor)

    outcome = facade.process(PYTHON_INPUT)

    assert outcome == completed
    assert isinstance(processor, ProcessDataset)
    assert processor.calls == (PythonRequestBuilder(CATALOG).build(PYTHON_INPUT),)
    assert not hasattr(facade, "_exporter")


def test_future_grpc_mapper_is_signature_only() -> None:
    assert FutureGrpcRequestMapper.__module__.endswith("delivery.request_mapping")
    assert callable(getattr(FutureGrpcRequestMapper, "to_application"))


def test_delivery_examples_import_no_framework_or_concrete_adapter() -> None:
    violations: list[str] = []
    forbidden = {"adapters", "argparse", "grpc", "google", "pandas"}

    for source_file in sorted(DELIVERY_ROOT.glob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = (node.module,)
            else:
                imported = ()
            for name in imported:
                if any(part in forbidden for part in name.split(".")):
                    violations.append(f"{source_file.name}:{node.lineno}:{name}")

    assert violations == []


class RecordingProcessor:
    def __init__(self, outcome: ProcessOutcome) -> None:
        self._outcome = outcome
        self._calls: list[ProcessingRequest] = []

    @property
    def calls(self) -> tuple[ProcessingRequest, ...]:
        return tuple(self._calls)

    def execute(self, request: ProcessingRequest) -> ProcessOutcome:
        self._calls.append(request)
        return self._outcome


class CannedExporter:
    def __init__(self, outcome: ExportOutcome) -> None:
        self._outcome = outcome
        self.calls: list[ExportRequest] = []

    def export(self, request: ExportRequest) -> ExportOutcome:
        self.calls.append(request)
        return self._outcome


def make_report(status: ReportStatus) -> ExecutionReport:
    scope = RequestedScope(
        ScopeId("scope.selection"),
        AXIS,
        Quantity(Decimal("500"), METRE),
        Quantity(Decimal("700"), METRE),
    )
    resolved = ResolvedScope(
        scope,
        scope.start,
        scope.end,
        BoundaryMode.EXACT,
    )
    binding = DatasetBinding(
        DatasetRole("primary"),
        DatasetReference("dataset-primary"),
        IngestionProfileReference("example.in_memory_v1"),
    )
    succeeded = ExecutionInstanceStatusRecord(
        ExecutionInstanceId("instance.example.success"),
        CalculationNodeId("example.success"),
        scope.id,
        None,
        NodeStatus.SUCCEEDED,
    )
    failed = ExecutionInstanceStatusRecord(
        ExecutionInstanceId("instance.example.failed"),
        CalculationNodeId("example.failed"),
        scope.id,
        None,
        NodeStatus.FAILED,
        FailureDetail(
            FailureCategory.NODE,
            "PLUGIN_EXCEPTION",
            "Plugin execution failed.",
        ),
    )
    instances = {
        ReportStatus.SUCCESS: (succeeded,),
        ReportStatus.PARTIAL_SUCCESS: (succeeded, failed),
        ReportStatus.FAILED: (failed,),
    }[status]
    return ExecutionReport(
        CompiledPlanId("plan.example"),
        DatasetBindings((binding,)),
        scope,
        resolved,
        status,
        (),
        instances,
    )
