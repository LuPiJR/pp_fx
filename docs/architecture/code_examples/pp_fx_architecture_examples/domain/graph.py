"""Typed static-artifact and scope-edge graph values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import ArtifactId, CalculationNodeId


class ArtifactKind(StrEnum):
    RAW_CHANNEL = "raw_channel"
    PARAMETER = "parameter"
    DERIVED_CHANNEL = "derived_channel"
    DETECTED_EVENT_SET = "detected_event_set"
    DETECTED_WINDOW_SET = "detected_window_set"
    SCALAR_KPI = "scalar_kpi"
    METRIC = "metric"


class ScopeEdgeMode(StrEnum):
    """How a dependency crosses runtime scope-instance boundaries."""

    SAME_SCOPE = "same_scope"
    EACH_SELECTED_CHILD_SCOPE = "each_selected_child_scope"
    FAN_IN_SELECTED_CHILDREN = "fan_in_selected_children"


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    artifact: ArtifactId
    kind: ArtifactKind
    scope_mode: ScopeEdgeMode


@dataclass(frozen=True, slots=True)
class ArtifactOutput:
    artifact: ArtifactId
    kind: ArtifactKind


@dataclass(frozen=True, slots=True)
class ArtifactSource:
    """An externally supplied artifact with no calculation-node producer."""

    output: ArtifactOutput


@dataclass(frozen=True, slots=True)
class ArtifactDependency:
    """A typed producer-to-consumer relation for one artifact."""

    producer: CalculationNodeId
    consumer: CalculationNodeId
    artifact: ArtifactId
    kind: ArtifactKind
    scope_mode: ScopeEdgeMode

    def __post_init__(self) -> None:
        if self.producer == self.consumer:
            raise ValueError("A calculation node cannot depend directly on itself.")
