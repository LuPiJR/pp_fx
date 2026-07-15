"""Immutable runtime-instance, occurrence-selection, and causal-flow values."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from ...domain.failures import FailureCategory, FailureDetail
from ...domain.graph import ArtifactDependency, ScopeEdgeMode
from ...domain.identifiers import (
    CalculationNodeId,
    ExecutionInstanceId,
    OccurrenceId,
    ScopeId,
)
from ...domain.results import NodeStatus
from ...domain.scopes import ResolvedScope
from ...domain.windows import DetectedWindow, WindowOccurrenceIssue
from .datasets import DatasetFingerprint


@dataclass(frozen=True, slots=True)
class DatasetFingerprintSet:
    """Canonical identity of every dataset participating in one execution."""

    values: tuple[DatasetFingerprint, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("An execution requires at least one dataset fingerprint.")
        if len(self.values) != len(set(self.values)):
            raise ValueError("Dataset fingerprints must be unique.")
        if self.values != tuple(sorted(self.values, key=lambda value: value.value)):
            raise ValueError("Dataset fingerprints must use canonical sorted order.")


@dataclass(frozen=True, slots=True)
class ExecutionInstanceKey:
    """Stable runtime identity before conversion to a report identifier."""

    node_id: CalculationNodeId
    dataset_fingerprints: DatasetFingerprintSet
    scope_id: ScopeId
    occurrence_id: OccurrenceId | None

    @property
    def execution_instance_id(self) -> ExecutionInstanceId:
        fingerprint_digest = hashlib.sha256(
            "\x1f".join(
                fingerprint.value
                for fingerprint in self.dataset_fingerprints.values
            ).encode("utf-8")
        ).hexdigest()[:16]
        occurrence = (
            self.occurrence_id.value
            if self.occurrence_id is not None
            else "occurrence.parent"
        )
        return ExecutionInstanceId(
            f"instance.{self.node_id.value}.{self.scope_id.value}."
            f"dataset_{fingerprint_digest}.{occurrence}"
        )


class OccurrenceSelectionMode(StrEnum):
    ALL = "all"
    FIRST = "first"
    LAST = "last"
    SPECIFIC = "specific"
    REQUIRE_EXACTLY_ONE = "require_exactly_one"


@dataclass(frozen=True, slots=True)
class OccurrenceSelector:
    mode: OccurrenceSelectionMode
    occurrence: OccurrenceId | None = None

    def __post_init__(self) -> None:
        is_specific = self.mode is OccurrenceSelectionMode.SPECIFIC
        if is_specific != (self.occurrence is not None):
            raise ValueError("Only a specific selector accepts an occurrence ID.")


@dataclass(frozen=True, slots=True)
class OccurrenceSelectionResult:
    parent_scope: ResolvedScope
    selected: tuple[DetectedWindow, ...]
    issues: tuple[WindowOccurrenceIssue, ...]
    failure: FailureDetail | None = None

    def __post_init__(self) -> None:
        if self.failure is not None:
            if self.failure.category is not FailureCategory.NODE:
                raise ValueError("Occurrence selection requires a node-level failure.")
            if self.selected:
                raise ValueError("A failed occurrence selection cannot select windows.")
        if any(window.scope.parent != self.parent_scope for window in self.selected):
            raise ValueError("Selected windows must belong to the selector parent scope.")


@dataclass(frozen=True, slots=True)
class RuntimeDependency:
    """One materialized relation between two scope-specific node instances."""

    static_edge: ArtifactDependency
    producer: ExecutionInstanceKey
    consumer: ExecutionInstanceKey

    def __post_init__(self) -> None:
        if self.producer.node_id != self.static_edge.producer:
            raise ValueError("A runtime producer must match its compiled edge.")
        if self.consumer.node_id != self.static_edge.consumer:
            raise ValueError("A runtime consumer must match its compiled edge.")
        if self.producer.dataset_fingerprints != self.consumer.dataset_fingerprints:
            raise ValueError("A runtime edge cannot cross dataset fingerprint sets.")

        mode = self.static_edge.scope_mode
        same_instance_scope = (
            self.producer.scope_id == self.consumer.scope_id
            and self.producer.occurrence_id == self.consumer.occurrence_id
        )
        if mode is ScopeEdgeMode.SAME_SCOPE and not same_instance_scope:
            raise ValueError("A same-scope edge must retain scope and occurrence identity.")
        if mode is ScopeEdgeMode.EACH_SELECTED_CHILD_SCOPE and (
            self.producer.occurrence_id is not None
            or self.consumer.occurrence_id is None
            or self.producer.scope_id == self.consumer.scope_id
        ):
            raise ValueError("A child edge must move from parent to one occurrence scope.")
        if mode is ScopeEdgeMode.FAN_IN_SELECTED_CHILDREN and (
            self.producer.occurrence_id is None
            or self.consumer.occurrence_id is not None
            or self.producer.scope_id == self.consumer.scope_id
        ):
            raise ValueError("A fan-in edge must move child occurrences to their parent.")


@dataclass(frozen=True, slots=True)
class CausalFailureRecord:
    """Node-level failure plus the runtime dependency that caused propagation."""

    detail: FailureDetail
    source_instance: ExecutionInstanceKey
    source_edge: ArtifactDependency

    def __post_init__(self) -> None:
        if self.detail.category is not FailureCategory.NODE:
            raise ValueError("Runtime failure propagation requires a node-level failure.")
        if self.source_instance.node_id != self.source_edge.producer:
            raise ValueError("A causal source must be the compiled edge producer.")


@dataclass(frozen=True, slots=True)
class RuntimeInstanceStatus:
    key: ExecutionInstanceKey
    status: NodeStatus
    cause: CausalFailureRecord | None = None

    def __post_init__(self) -> None:
        if self.status is NodeStatus.SUCCEEDED:
            if self.cause is not None:
                raise ValueError("A successful runtime instance has no failure cause.")
            return
        if self.cause is None:
            raise ValueError("A failed or blocked runtime instance requires a cause.")


@dataclass(frozen=True, slots=True)
class RuntimeMaterialization:
    instances: tuple[ExecutionInstanceKey, ...]
    dependencies: tuple[RuntimeDependency, ...]

    def __post_init__(self) -> None:
        if len(self.instances) != len(set(self.instances)):
            raise ValueError("Materialized execution instance keys must be unique.")
