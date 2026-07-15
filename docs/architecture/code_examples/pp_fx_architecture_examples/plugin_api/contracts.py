from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Mapping, Protocol, TypeVar

from .references import ChannelRef, ParameterRef, QuantityRef, UnitRef

ConfigurationT = TypeVar("ConfigurationT", covariant=True)
FrameT = TypeVar("FrameT", covariant=True)


class NodeKind(StrEnum):
    DERIVED_CHANNEL = "derived_channel"
    WINDOW_DETECTOR = "window_detector"
    KPI = "kpi"
    METRIC = "metric"


@dataclass(frozen=True, slots=True)
class ChannelRequirement:
    channel: ChannelRef
    unit: UnitRef | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class ParameterRequirement:
    parameter: ParameterRef
    unit: UnitRef | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class DatasetRequirement:
    role: str
    axis: ChannelRef
    required: bool = True

    def __post_init__(self) -> None:
        if not self.role:
            raise ValueError("A dataset role is required.")


@dataclass(frozen=True, slots=True)
class ResultRequirement:
    artifact: str

    def __post_init__(self) -> None:
        if not self.artifact:
            raise ValueError("A result artifact is required.")


@dataclass(frozen=True, slots=True)
class ContextRequirement:
    before_samples: int = 0
    after_samples: int = 0

    def __post_init__(self) -> None:
        if self.before_samples < 0 or self.after_samples < 0:
            raise ValueError("Context sample counts cannot be negative.")


@dataclass(frozen=True, slots=True)
class DerivedChannelDefinition:
    channel: ChannelRef
    quantity: QuantityRef
    unit: UnitRef


@dataclass(frozen=True, slots=True)
class WindowResultDefinition:
    artifact: str

    def __post_init__(self) -> None:
        if not self.artifact:
            raise ValueError("A window artifact is required.")


@dataclass(frozen=True, slots=True)
class ScalarResultDefinition:
    artifact: str
    quantity: QuantityRef
    unit: UnitRef

    def __post_init__(self) -> None:
        if not self.artifact:
            raise ValueError("A scalar-result artifact is required.")


NodeOutputDefinition = (
    DerivedChannelDefinition | WindowResultDefinition | ScalarResultDefinition
)


@dataclass(frozen=True, slots=True)
class NodeDeclaration:
    id: str
    kind: NodeKind
    function_name: str
    requires_channels: tuple[ChannelRequirement, ...]
    requires_parameters: tuple[ParameterRequirement, ...]
    requires_datasets: tuple[DatasetRequirement, ...]
    requires_results: tuple[ResultRequirement, ...]
    context: ContextRequirement
    configuration: type[object] | None
    output: NodeOutputDefinition

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("A node ID is required.")


@dataclass(frozen=True, slots=True)
class ParameterValue:
    value: int | float | str | bool
    unit: UnitRef | None = None


class ParameterView(Protocol):
    def get(self, parameter: ParameterRef) -> ParameterValue: ...


@dataclass(frozen=True, slots=True)
class PluginScope:
    id: str
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class DerivedChannelInput(Generic[ConfigurationT, FrameT]):
    frame: FrameT
    parameters: ParameterView
    datasets: Mapping[str, FrameT]
    scope: PluginScope
    configuration: ConfigurationT


@dataclass(frozen=True, slots=True)
class WindowDetectorInput(Generic[ConfigurationT, FrameT]):
    frame: FrameT
    parameters: ParameterView
    datasets: Mapping[str, FrameT]
    scope: PluginScope
    configuration: ConfigurationT


@dataclass(frozen=True, slots=True)
class KpiInput(Generic[ConfigurationT, FrameT]):
    frame: FrameT
    parameters: ParameterView
    datasets: Mapping[str, FrameT]
    scope: PluginScope
    configuration: ConfigurationT


@dataclass(frozen=True, slots=True)
class MetricInput(Generic[ConfigurationT]):
    results: Mapping[str, ScalarResult]
    configuration: ConfigurationT


@dataclass(frozen=True, slots=True)
class ScalarResult:
    value: float
    unit: UnitRef


@dataclass(frozen=True, slots=True)
class DetectedWindow:
    occurrence: str
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("A detected window cannot end before it starts.")


@dataclass(frozen=True, slots=True)
class WindowOccurrenceIssue:
    occurrence: str
    code: str


@dataclass(frozen=True, slots=True)
class WindowDetectionResult:
    completed: tuple[DetectedWindow, ...]
    issues: tuple[WindowOccurrenceIssue, ...] = ()
