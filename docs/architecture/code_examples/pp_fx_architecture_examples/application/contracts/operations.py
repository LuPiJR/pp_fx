"""Framework-neutral request/result values consumed by processing ports."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    DatasetRole,
)
from ...domain.results import ArtifactResult
from ...domain.scopes import RequestedScope, ResolvedScope
from .datasets import LoadedDataset, ParameterSet
from .policies import AlignmentPolicy, BoundaryPolicy, NormalizationPolicy
from .tables import TableHandle


@dataclass(frozen=True, slots=True)
class DiagnosticChange:
    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("A diagnostic change requires a code and message.")


@dataclass(frozen=True, slots=True)
class NormalizationReport:
    changes: tuple[DiagnosticChange, ...]


@dataclass(frozen=True, slots=True)
class AlignmentReport:
    changes: tuple[DiagnosticChange, ...]


@dataclass(frozen=True, slots=True)
class ScopeResolutionRequest:
    dataset: LoadedDataset
    scope: RequestedScope
    boundary_policy: BoundaryPolicy


@dataclass(frozen=True, slots=True)
class ScopeResolutionResult:
    dataset: LoadedDataset
    scope: ResolvedScope


@dataclass(frozen=True, slots=True)
class NormalizationRequest:
    dataset: LoadedDataset
    policy: NormalizationPolicy


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    dataset: LoadedDataset
    report: NormalizationReport


@dataclass(frozen=True, slots=True)
class ContextRequirementSpec:
    before_samples: int = 0
    after_samples: int = 0

    def __post_init__(self) -> None:
        if self.before_samples < 0 or self.after_samples < 0:
            raise ValueError("Context sample requirements cannot be negative.")


@dataclass(frozen=True, slots=True)
class ContextExpansionRequest:
    dataset: LoadedDataset
    scope: ResolvedScope
    requirement: ContextRequirementSpec


@dataclass(frozen=True, slots=True)
class ContextExpansionResult:
    dataset: LoadedDataset
    target_scope: ResolvedScope
    available_before_samples: int
    available_after_samples: int

    def __post_init__(self) -> None:
        if self.available_before_samples < 0 or self.available_after_samples < 0:
            raise ValueError("Available context sample counts cannot be negative.")


@dataclass(frozen=True, slots=True)
class DatasetAlignmentRequest:
    primary: ContextExpansionResult
    comparisons: tuple[LoadedDataset, ...]
    policy: AlignmentPolicy

    def __post_init__(self) -> None:
        if self.primary.dataset.binding.role != DatasetRole("primary"):
            raise ValueError("Dataset alignment requires the primary dataset role.")
        roles = tuple(dataset.binding.role for dataset in self.comparisons)
        if DatasetRole("primary") in roles or len(roles) != len(set(roles)):
            raise ValueError("Comparison dataset roles must be unique and non-primary.")


@dataclass(frozen=True, slots=True)
class RoleTable:
    role: DatasetRole
    table: TableHandle


@dataclass(frozen=True, slots=True)
class AlignedDatasets:
    values: tuple[RoleTable, ...]
    report: AlignmentReport

    def __post_init__(self) -> None:
        roles = tuple(value.role for value in self.values)
        if roles.count(DatasetRole("primary")) != 1:
            raise ValueError("Aligned datasets require exactly one primary role.")
        if len(roles) != len(set(roles)):
            raise ValueError("Aligned dataset roles must be unique.")


@dataclass(frozen=True, slots=True)
class PreparedNodeInput:
    datasets: tuple[RoleTable, ...]
    parameters: ParameterSet
    scope: ResolvedScope
    scalar_artifacts: tuple[ArtifactResult, ...] = ()
    table_artifacts: tuple[ProducedTableArtifact, ...] = ()

    def __post_init__(self) -> None:
        roles = tuple(dataset.role for dataset in self.datasets)
        if roles.count(DatasetRole("primary")) != 1:
            raise ValueError("Prepared node input requires exactly one primary dataset.")
        if len(roles) != len(set(roles)):
            raise ValueError("Prepared node dataset roles must be unique.")
        artifact_ids = tuple(
            artifact.artifact_id for artifact in self.scalar_artifacts
        ) + tuple(artifact.id for artifact in self.table_artifacts)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("Prepared node artifacts must have unique IDs.")


@dataclass(frozen=True, slots=True)
class ProducedTableArtifact:
    id: ArtifactId
    table: TableHandle


@dataclass(frozen=True, slots=True)
class PluginExecutionResult:
    node_id: CalculationNodeId
    scalar_results: tuple[ArtifactResult, ...]
    table_artifacts: tuple[ProducedTableArtifact, ...]

    def __post_init__(self) -> None:
        artifact_ids = tuple(
            result.artifact_id for result in self.scalar_results
        ) + tuple(artifact.id for artifact in self.table_artifacts)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("Plugin execution artifact IDs must be unique.")
