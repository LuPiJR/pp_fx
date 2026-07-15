"""Deterministic detected-window fan-out; no plugin invocation or parallelism."""

from __future__ import annotations

from ...domain.failures import FailureCategory, FailureDetail
from ...domain.graph import ArtifactDependency, ScopeEdgeMode
from ...domain.identifiers import CalculationNodeId
from ...domain.results import NodeStatus
from ...domain.windows import WindowDetectionResult
from ..contracts.execution import (
    CausalFailureRecord,
    ExecutionInstanceKey,
    OccurrenceSelectionMode,
    OccurrenceSelectionResult,
    OccurrenceSelector,
    RuntimeDependency,
    RuntimeInstanceStatus,
    RuntimeMaterialization,
)
from ..contracts.plans import TargetClosure


def select_occurrences(
    detection: WindowDetectionResult,
    selector: OccurrenceSelector,
) -> OccurrenceSelectionResult:
    """Apply one explicit cardinality policy without discarding detector issues."""

    completed = detection.completed
    if selector.mode is OccurrenceSelectionMode.ALL:
        selected = completed
    elif selector.mode is OccurrenceSelectionMode.FIRST:
        selected = completed[:1]
    elif selector.mode is OccurrenceSelectionMode.LAST:
        selected = completed[-1:]
    elif selector.mode is OccurrenceSelectionMode.SPECIFIC:
        selected = tuple(
            window
            for window in completed
            if window.occurrence == selector.occurrence
        )
        if not selected:
            return _selection_failure(
                detection,
                "OCCURRENCE_NOT_FOUND",
                f"Occurrence {selector.occurrence} is not a completed window.",
            )
    else:
        if len(completed) != 1:
            return _selection_failure(
                detection,
                "OCCURRENCE_CARDINALITY",
                f"Exactly one completed occurrence is required; found {len(completed)}.",
            )
        selected = completed

    return OccurrenceSelectionResult(
        parent_scope=detection.parent_scope,
        selected=selected,
        issues=detection.issues,
    )


def materialize_selected_children(
    edge: ArtifactDependency,
    detector: ExecutionInstanceKey,
    selection: OccurrenceSelectionResult,
) -> RuntimeMaterialization:
    """Create one consumer instance for every selected complete child window."""

    if edge.scope_mode is not ScopeEdgeMode.EACH_SELECTED_CHILD_SCOPE:
        raise ValueError("Child materialization requires an explicit child-scope edge.")
    if detector.node_id != edge.producer:
        raise ValueError("The detector instance must match the child-edge producer.")
    if detector.scope_id != selection.parent_scope.id or detector.occurrence_id is not None:
        raise ValueError("The detector must execute once in the selection parent scope.")
    if selection.failure is not None:
        return RuntimeMaterialization((), ())

    instances = tuple(
        ExecutionInstanceKey(
            node_id=edge.consumer,
            dataset_fingerprints=detector.dataset_fingerprints,
            scope_id=window.scope.id,
            occurrence_id=window.occurrence,
        )
        for window in selection.selected
    )
    dependencies = tuple(
        RuntimeDependency(edge, detector, instance)
        for instance in instances
    )
    return RuntimeMaterialization(instances, dependencies)


def materialize_explicit_fan_in(
    edge: ArtifactDependency,
    parent: ExecutionInstanceKey,
    child_producers: tuple[ExecutionInstanceKey, ...],
) -> RuntimeMaterialization:
    """Create one parent consumer only when the compiled edge explicitly permits fan-in."""

    if edge.scope_mode is not ScopeEdgeMode.FAN_IN_SELECTED_CHILDREN:
        raise ValueError("Runtime aggregation requires an explicit fan-in edge.")
    if parent.occurrence_id is not None:
        raise ValueError("A fan-in parent cannot identify one child occurrence.")
    if not child_producers:
        return RuntimeMaterialization((), ())
    if any(
        child.node_id != edge.producer
        or child.dataset_fingerprints != parent.dataset_fingerprints
        or child.occurrence_id is None
        for child in child_producers
    ):
        raise ValueError("Fan-in producers must be occurrence instances of the edge producer.")

    consumer = ExecutionInstanceKey(
        node_id=edge.consumer,
        dataset_fingerprints=parent.dataset_fingerprints,
        scope_id=parent.scope_id,
        occurrence_id=None,
    )
    dependencies = tuple(
        RuntimeDependency(edge, child, consumer)
        for child in child_producers
    )
    return RuntimeMaterialization((consumer,), dependencies)


def block_selector_descendants(
    closure: TargetClosure,
    selector_edge: ArtifactDependency,
    detector: ExecutionInstanceKey,
    selection: OccurrenceSelectionResult,
) -> tuple[RuntimeInstanceStatus, ...]:
    """Materialize only the runtime descendants blocked by a selector failure."""

    if selection.failure is None:
        return ()
    if selector_edge.scope_mode is not ScopeEdgeMode.EACH_SELECTED_CHILD_SCOPE:
        raise ValueError("Selector blocking requires an explicit child-scope edge.")
    if selector_edge not in closure.edges:
        raise ValueError("The selector edge must belong to the selected target closure.")
    if detector.node_id != selector_edge.producer:
        raise ValueError("The detector instance must match the selector-edge producer.")
    if detector.scope_id != selection.parent_scope.id or detector.occurrence_id is not None:
        raise ValueError("Selector failure must belong to the detector parent instance.")

    descendants = _descendants(selector_edge.consumer, closure)
    cause = CausalFailureRecord(selection.failure, detector, selector_edge)
    return tuple(
        RuntimeInstanceStatus(
            key=ExecutionInstanceKey(
                node_id=node_id,
                dataset_fingerprints=detector.dataset_fingerprints,
                scope_id=detector.scope_id,
                occurrence_id=None,
            ),
            status=NodeStatus.NOT_CALCULATED,
            cause=cause,
        )
        for node_id in closure.node_ids
        if node_id in descendants
    )


def _selection_failure(
    detection: WindowDetectionResult,
    code: str,
    message: str,
) -> OccurrenceSelectionResult:
    return OccurrenceSelectionResult(
        parent_scope=detection.parent_scope,
        selected=(),
        issues=detection.issues,
        failure=FailureDetail(FailureCategory.NODE, code, message),
    )


def _descendants(
    root: CalculationNodeId,
    closure: TargetClosure,
) -> set[CalculationNodeId]:
    descendants = {root}
    pending = [root]
    while pending:
        producer = pending.pop()
        for edge in closure.edges:
            if edge.producer == producer and edge.consumer not in descendants:
                descendants.add(edge.consumer)
                pending.append(edge.consumer)
    return descendants
