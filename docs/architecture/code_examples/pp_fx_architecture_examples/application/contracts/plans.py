"""Serializable immutable shapes produced by plan compilation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ...domain.graph import (
    ArtifactDependency,
    ArtifactInput,
    ArtifactOutput,
    ArtifactSource,
)
from ...domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    CatalogId,
    ChannelId,
    CompiledPlanId,
    DatasetRole,
    FunctionPackId,
    ParameterId,
    ProcessingTargetId,
)
from ...domain.units import QuantityKind, Unit

_HASH_ALGORITHM = re.compile(r"^[a-z][a-z0-9]*$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]+$")
ConfigurationValue: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class ContentHash:
    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if not _HASH_ALGORITHM.fullmatch(self.algorithm):
            raise ValueError("A content-hash algorithm must be a lowercase identifier.")
        if not _HEX_DIGEST.fullmatch(self.digest):
            raise ValueError("A content-hash digest must be lowercase hexadecimal.")
        if self.algorithm == "sha256" and len(self.digest) != 64:
            raise ValueError("A sha256 digest must contain 64 hexadecimal characters.")


@dataclass(frozen=True, slots=True)
class NodeConfigurationEntry:
    key: str
    value: ConfigurationValue

    def __post_init__(self) -> None:
        if not self.key or self.key != self.key.strip():
            raise ValueError("A node-configuration key must be non-empty and trimmed.")
        if not isinstance(self.value, (str, int, float, bool, type(None))):
            raise TypeError("A compiled node configuration value must be serializable.")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("A compiled node configuration value must be finite.")


@dataclass(frozen=True, slots=True)
class FunctionPackLock:
    id: FunctionPackId
    version: str
    distribution_hash: ContentHash
    declaration_hash: ContentHash

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("A locked function pack requires an exact version.")


@dataclass(frozen=True, slots=True)
class CatalogLock:
    id: CatalogId
    version: str
    content_hash: ContentHash

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("A locked catalog requires an exact version.")


class CompiledNodeKind(StrEnum):
    DERIVED_CHANNEL = "derived_channel"
    WINDOW_DETECTOR = "window_detector"
    KPI = "kpi"
    METRIC = "metric"


@dataclass(frozen=True, slots=True)
class CompiledChannelInput:
    channel: ChannelId
    artifact: ArtifactId
    calculation_unit: Unit | None
    required: bool


@dataclass(frozen=True, slots=True)
class CompiledParameterInput:
    parameter: ParameterId
    artifact: ArtifactId
    calculation_unit: Unit | None
    required: bool


@dataclass(frozen=True, slots=True)
class CompiledDatasetInput:
    role: DatasetRole
    axis: ChannelId
    axis_artifact: ArtifactId
    required: bool


@dataclass(frozen=True, slots=True)
class CompiledContext:
    before_samples: int = 0
    after_samples: int = 0

    def __post_init__(self) -> None:
        if self.before_samples < 0 or self.after_samples < 0:
            raise ValueError("Compiled context sample counts cannot be negative.")


@dataclass(frozen=True, slots=True)
class CompiledOutput:
    artifact: ArtifactId
    quantity_kind: QuantityKind | None = None
    calculation_unit: Unit | None = None

    def __post_init__(self) -> None:
        if (self.quantity_kind is None) != (self.calculation_unit is None):
            raise ValueError("A compiled output requires both quantity and unit or neither.")
        if (
            self.quantity_kind is not None
            and self.calculation_unit is not None
            and self.quantity_kind != self.calculation_unit.quantity_kind
        ):
            raise ValueError("A compiled output unit must match its quantity kind.")


@dataclass(frozen=True, slots=True)
class CompiledNodeSpec:
    """Runtime-owned node identity and values; never a Python callable."""

    id: CalculationNodeId
    pack: FunctionPackLock
    consumes: tuple[ArtifactId, ...]
    produces: tuple[ArtifactId, ...]
    configuration: tuple[NodeConfigurationEntry, ...] = ()
    kind: CompiledNodeKind | None = None
    channel_inputs: tuple[CompiledChannelInput, ...] = ()
    parameter_inputs: tuple[CompiledParameterInput, ...] = ()
    dataset_inputs: tuple[CompiledDatasetInput, ...] = ()
    context: CompiledContext = CompiledContext()
    output: CompiledOutput | None = None

    def __post_init__(self) -> None:
        if not self.produces:
            raise ValueError("A compiled node must produce at least one artifact.")
        if len(self.consumes) != len(set(self.consumes)):
            raise ValueError("A compiled node cannot repeat consumed artifacts.")
        if len(self.produces) != len(set(self.produces)):
            raise ValueError("A compiled node cannot repeat produced artifacts.")
        configuration_keys = tuple(entry.key for entry in self.configuration)
        if len(configuration_keys) != len(set(configuration_keys)):
            raise ValueError("Compiled node configuration keys must be unique.")

        declared_inputs = {item.artifact for item in self.channel_inputs}
        declared_inputs.update(item.artifact for item in self.parameter_inputs)
        declared_inputs.update(item.axis_artifact for item in self.dataset_inputs)
        if not declared_inputs.issubset(self.consumes):
            raise ValueError("Compiled input details must reference consumed artifacts.")
        if self.output is not None and self.output.artifact not in self.produces:
            raise ValueError("A compiled output must reference a produced artifact.")


@dataclass(frozen=True, slots=True)
class ProcessingTarget:
    """A named public export surface, never an internal node selection."""

    id: ProcessingTargetId
    exports: tuple[ArtifactId, ...]

    def __post_init__(self) -> None:
        if not self.exports:
            raise ValueError("A processing target must export at least one artifact.")
        if len(self.exports) != len(set(self.exports)):
            raise ValueError("A processing target cannot repeat exported artifacts.")


@dataclass(frozen=True, slots=True)
class GraphNodeSpec:
    """A mapped node plus plan-resolved typed artifact contracts."""

    specification: CompiledNodeSpec
    inputs: tuple[ArtifactInput, ...]
    outputs: tuple[ArtifactOutput, ...]


class GraphValidationCode(StrEnum):
    DUPLICATE_NODE = "duplicate_node"
    DUPLICATE_SOURCE = "duplicate_source"
    DUPLICATE_PRODUCER = "duplicate_producer"
    MISSING_PRODUCER = "missing_producer"
    ARTIFACT_TYPE_MISMATCH = "artifact_type_mismatch"
    NODE_CONTRACT_MISMATCH = "node_contract_mismatch"
    INVALID_SOURCE_SCOPE = "invalid_source_scope"
    DUPLICATE_TARGET = "duplicate_target"
    MISSING_TARGET_EXPORT = "missing_target_export"
    CYCLE = "cycle"


@dataclass(frozen=True, slots=True)
class GraphValidationFailure:
    code: GraphValidationCode
    reference: str
    message: str

    def __post_init__(self) -> None:
        if not self.reference or not self.message:
            raise ValueError("A graph validation failure requires reference and detail.")


@dataclass(frozen=True, slots=True)
class StaticGraphValidationResult:
    failures: tuple[GraphValidationFailure, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.failures


@dataclass(frozen=True, slots=True)
class CompiledGraph:
    sources: tuple[ArtifactSource, ...]
    nodes: tuple[GraphNodeSpec, ...]
    edges: tuple[ArtifactDependency, ...]
    targets: tuple[ProcessingTarget, ...]
    topological_order: tuple[CalculationNodeId, ...]

    def __post_init__(self) -> None:
        node_ids = tuple(node.specification.id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("A compiled graph requires unique node IDs.")
        if (
            len(self.topological_order) != len(node_ids)
            or set(node_ids) != set(self.topological_order)
        ):
            raise ValueError("Topological order must contain every graph node exactly once.")


@dataclass(frozen=True, slots=True)
class GraphCompilationResult:
    graph: CompiledGraph | None
    validation: StaticGraphValidationResult

    def __post_init__(self) -> None:
        if self.validation.is_valid != (self.graph is not None):
            raise ValueError("Only a valid graph compilation may contain a graph.")


@dataclass(frozen=True, slots=True)
class TargetClosure:
    target_ids: tuple[ProcessingTargetId, ...]
    exports: tuple[ArtifactId, ...]
    node_ids: tuple[CalculationNodeId, ...]
    edges: tuple[ArtifactDependency, ...]


@dataclass(frozen=True, slots=True)
class CompiledPlan:
    id: CompiledPlanId
    plugin_api_version: str
    unit_registry_version: str
    function_packs: tuple[FunctionPackLock, ...]
    catalogs: tuple[CatalogLock, ...]
    graph: CompiledGraph

    def __post_init__(self) -> None:
        if not self.plugin_api_version or not self.unit_registry_version:
            raise ValueError("A compiled plan requires API and unit-registry versions.")
        _require_unique_ids(self.function_packs, "function-pack")
        _require_unique_ids(self.catalogs, "catalog")

        locked_packs = set(self.function_packs)
        if any(node.pack not in locked_packs for node in self.nodes):
            raise ValueError("Every compiled node must use a locked function pack.")

    @property
    def nodes(self) -> tuple[CompiledNodeSpec, ...]:
        return tuple(node.specification for node in self.graph.nodes)

    @property
    def targets(self) -> tuple[ProcessingTarget, ...]:
        return self.graph.targets


def _require_unique_ids(values: tuple[object, ...], kind: str) -> None:
    ids = tuple(getattr(value, "id") for value in values)
    if len(ids) != len(set(ids)):
        raise ValueError(f"Compiled plan {kind} IDs must be unique.")
