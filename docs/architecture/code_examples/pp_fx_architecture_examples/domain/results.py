"""Typed artifact result, status, provenance, and failure values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from .failures import FailureCategory, FailureDetail
from .identifiers import ArtifactId, CalculationNodeId
from .units import Quantity, Unit

ResultValue: TypeAlias = Quantity | bool | str


class NodeStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_CALCULATED = "not_calculated"


@dataclass(frozen=True, slots=True)
class ResultProvenance:
    """Domain facts needed to explain where one artifact value came from."""

    node_id: CalculationNodeId
    input_artifacts: tuple[ArtifactId, ...]
    calculation_unit: Unit | None = None

    def __post_init__(self) -> None:
        if len(set(self.input_artifacts)) != len(self.input_artifacts):
            raise ValueError("Result provenance cannot repeat an input artifact.")


@dataclass(frozen=True, slots=True)
class ArtifactResult:
    """One typed artifact outcome with status-consistent optional fields."""

    artifact_id: ArtifactId
    status: NodeStatus
    value: ResultValue | None = None
    provenance: ResultProvenance | None = None
    failure: FailureDetail | None = None

    def __post_init__(self) -> None:
        if self.status is NodeStatus.SUCCEEDED:
            self._validate_success()
            return

        if self.value is not None:
            raise ValueError("A failed or skipped result cannot carry a value.")
        if self.failure is None:
            raise ValueError(f"Status {self.status.value} requires a failure.")
        if self.failure.category is not FailureCategory.NODE:
            raise ValueError("An artifact result requires a node-level failure.")
        if self.status is NodeStatus.NOT_CALCULATED and self.provenance is not None:
            raise ValueError("A result that was not calculated has no provenance.")

    def _validate_success(self) -> None:
        if self.value is None:
            raise ValueError("A succeeded result requires a value.")
        if not isinstance(self.value, (Quantity, bool, str)):
            raise ValueError("A numeric result must be a typed Quantity with a unit.")
        if isinstance(self.value, str) and not self.value:
            raise ValueError("A textual result must not be empty.")
        if self.provenance is None:
            raise ValueError("A succeeded result requires provenance.")
        if self.failure is not None:
            raise ValueError("A succeeded result cannot carry a failure.")
