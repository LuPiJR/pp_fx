from __future__ import annotations

from decimal import Decimal

import pytest

from pp_fx_architecture_examples.application.contracts.datasets import DatasetFingerprint
from pp_fx_architecture_examples.application.contracts.execution import (
    DatasetFingerprintSet,
    ExecutionInstanceKey,
    OccurrenceSelectionMode,
    OccurrenceSelector,
)
from pp_fx_architecture_examples.application.contracts.plans import TargetClosure
from pp_fx_architecture_examples.application.contracts.reports import ResultRecord
from pp_fx_architecture_examples.application.services.occurrence_scheduler import (
    block_selector_descendants,
    materialize_explicit_fan_in,
    materialize_selected_children,
    select_occurrences,
)
from pp_fx_architecture_examples.domain.failures import FailureCategory, FailureDetail
from pp_fx_architecture_examples.domain.graph import (
    ArtifactDependency,
    ArtifactKind,
    ScopeEdgeMode,
)
from pp_fx_architecture_examples.domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    ChannelId,
    DatasetRole,
    OccurrenceId,
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
from pp_fx_architecture_examples.domain.windows import (
    DetectedWindow,
    WindowDetectionResult,
    WindowOccurrenceIssue,
)

DISTANCE = QuantityKind("distance")
METRE = Unit("si.metre", "m", DISTANCE)
AXIS = CoordinateAxis(ChannelId("lap.distance"), DISTANCE, METRE)


def resolved_scope(scope_id: str, start: Decimal, end: Decimal) -> ResolvedScope:
    requested = RequestedScope(
        ScopeId(scope_id),
        AXIS,
        Quantity(start, METRE),
        Quantity(end, METRE),
    )
    return ResolvedScope(
        requested,
        requested.start,
        requested.end,
        BoundaryMode.EXACT,
    )


DETECTOR = CalculationNodeId("example.brake_detector")
KPI = CalculationNodeId("example.brake_kpi")
METRIC = CalculationNodeId("example.brake_metric")
INDEPENDENT = CalculationNodeId("example.aero_kpi")
WINDOWS = ArtifactId("detected.brake.windows")
KPI_RESULT = ArtifactId("result.brake.energy")
FINGERPRINTS = DatasetFingerprintSet(
    (DatasetFingerprint("sha256:" + "a" * 64),)
)
PARENT = resolved_scope("scope.sector_two", Decimal("500"), Decimal("700"))
DETECTOR_KEY = ExecutionInstanceKey(DETECTOR, FINGERPRINTS, PARENT.id, None)
CHILD_EDGE = ArtifactDependency(
    DETECTOR,
    KPI,
    WINDOWS,
    ArtifactKind.DETECTED_WINDOW_SET,
    ScopeEdgeMode.EACH_SELECTED_CHILD_SCOPE,
)
FAN_IN_EDGE = ArtifactDependency(
    KPI,
    METRIC,
    KPI_RESULT,
    ArtifactKind.SCALAR_KPI,
    ScopeEdgeMode.FAN_IN_SELECTED_CHILDREN,
)


def test_two_selected_windows_create_two_child_execution_keys() -> None:
    detection = detection_result(include_incomplete=False)
    selection = select_occurrences(
        detection,
        OccurrenceSelector(OccurrenceSelectionMode.ALL),
    )

    materialized = materialize_selected_children(
        CHILD_EDGE,
        DETECTOR_KEY,
        selection,
    )

    assert materialized.instances == (
        ExecutionInstanceKey(
            KPI,
            FINGERPRINTS,
            ScopeId("scope.brake_one"),
            OccurrenceId("occurrence.brake_one"),
        ),
        ExecutionInstanceKey(
            KPI,
            FINGERPRINTS,
            ScopeId("scope.brake_two"),
            OccurrenceId("occurrence.brake_two"),
        ),
    )
    assert tuple(dependency.producer for dependency in materialized.dependencies) == (
        DETECTOR_KEY,
        DETECTOR_KEY,
    )


def test_incomplete_trailing_occurrence_does_not_block_completed_siblings() -> None:
    detection = detection_result(include_incomplete=True)
    selection = select_occurrences(
        detection,
        OccurrenceSelector(OccurrenceSelectionMode.ALL),
    )

    materialized = materialize_selected_children(
        CHILD_EDGE,
        DETECTOR_KEY,
        selection,
    )

    assert len(materialized.instances) == 2
    assert tuple(window.occurrence for window in selection.selected) == (
        OccurrenceId("occurrence.brake_one"),
        OccurrenceId("occurrence.brake_two"),
    )
    assert detection.issues[0].failure.code == "INCOMPLETE_WINDOW"


def test_exactly_one_failure_blocks_only_selector_descendants() -> None:
    selection = select_occurrences(
        detection_result(include_incomplete=False),
        OccurrenceSelector(OccurrenceSelectionMode.REQUIRE_EXACTLY_ONE),
    )
    closure = TargetClosure(
        target_ids=(ProcessingTargetId("target.braking"),),
        exports=(KPI_RESULT,),
        node_ids=(DETECTOR, KPI, METRIC, INDEPENDENT),
        edges=(
            CHILD_EDGE,
            ArtifactDependency(
                KPI,
                METRIC,
                KPI_RESULT,
                ArtifactKind.SCALAR_KPI,
                ScopeEdgeMode.SAME_SCOPE,
            ),
        ),
    )

    blocked = block_selector_descendants(
        closure,
        CHILD_EDGE,
        DETECTOR_KEY,
        selection,
    )

    assert selection.failure is not None
    assert selection.failure.code == "OCCURRENCE_CARDINALITY"
    assert tuple(status.key.node_id for status in blocked) == (KPI, METRIC)
    assert all(status.status is NodeStatus.NOT_CALCULATED for status in blocked)
    assert all(status.cause.source_edge == CHILD_EDGE for status in blocked)
    assert INDEPENDENT not in {status.key.node_id for status in blocked}


def test_fan_in_materializes_only_for_an_explicit_fan_in_edge() -> None:
    selection = select_occurrences(
        detection_result(include_incomplete=False),
        OccurrenceSelector(OccurrenceSelectionMode.ALL),
    )
    children = materialize_selected_children(
        CHILD_EDGE,
        DETECTOR_KEY,
        selection,
    )

    fan_in = materialize_explicit_fan_in(
        FAN_IN_EDGE,
        DETECTOR_KEY,
        children.instances,
    )

    assert fan_in.instances == (
        ExecutionInstanceKey(METRIC, FINGERPRINTS, PARENT.id, None),
    )
    assert tuple(dependency.producer for dependency in fan_in.dependencies) == (
        *children.instances,
    )
    assert all(
        dependency.static_edge.scope_mode
        is ScopeEdgeMode.FAN_IN_SELECTED_CHILDREN
        for dependency in fan_in.dependencies
    )

    with pytest.raises(ValueError, match="explicit fan-in"):
        materialize_explicit_fan_in(
            ArtifactDependency(
                KPI,
                METRIC,
                KPI_RESULT,
                ArtifactKind.SCALAR_KPI,
                ScopeEdgeMode.SAME_SCOPE,
            ),
            DETECTOR_KEY,
            children.instances,
        )


def test_scope_ancestry_and_occurrence_identity_reach_result_record() -> None:
    window = detection_result(include_incomplete=False).completed[0]
    key = ExecutionInstanceKey(
        KPI,
        FINGERPRINTS,
        window.scope.id,
        window.occurrence,
    )
    artifact = ArtifactResult(
        artifact_id=KPI_RESULT,
        status=NodeStatus.SUCCEEDED,
        value=Quantity(Decimal("42"), METRE),
        provenance=ResultProvenance(KPI, (WINDOWS,), METRE),
    )

    record = ResultRecord(
        node_id=key.node_id,
        execution_instance=key.execution_instance_id,
        target_id=ProcessingTargetId("target.braking"),
        dataset_role=DatasetRole("primary"),
        scope=key.scope_id,
        occurrence=key.occurrence_id,
        scope_ancestry=window.scope.ancestry,
        artifact=artifact,
    )

    assert record.scope_ancestry == (PARENT.id, window.scope.id)
    assert record.occurrence == window.occurrence


def detection_result(*, include_incomplete: bool) -> WindowDetectionResult:
    first = detected_window(
        "scope.brake_one",
        "occurrence.brake_one",
        Decimal("520"),
        Decimal("540"),
    )
    second = detected_window(
        "scope.brake_two",
        "occurrence.brake_two",
        Decimal("600"),
        Decimal("630"),
    )
    issues = ()
    if include_incomplete:
        issues = (
            WindowOccurrenceIssue(
                occurrence=OccurrenceId("occurrence.brake_three"),
                parent_scope=PARENT.id,
                scope_ancestry=PARENT.ancestry,
                failure=FailureDetail(
                    FailureCategory.NODE,
                    "INCOMPLETE_WINDOW",
                    "The trailing brake application has no closing event.",
                ),
            ),
        )
    return WindowDetectionResult(PARENT, (first, second), issues)


def detected_window(
    scope_id: str,
    occurrence_id: str,
    start: Decimal,
    end: Decimal,
) -> DetectedWindow:
    return DetectedWindow(
        occurrence=OccurrenceId(occurrence_id),
        scope=ResolvedScope(
            requested=RequestedScope(
                id=ScopeId(scope_id),
                axis=AXIS,
                start=Quantity(start, METRE),
                end=Quantity(end, METRE),
            ),
            effective_start=Quantity(start, METRE),
            effective_end=Quantity(end, METRE),
            boundary_mode=BoundaryMode.EXACT,
            parent=PARENT,
        ),
    )
