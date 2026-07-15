"""The transport-neutral input contract for synchronous processing."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.identifiers import CompiledPlanId, ProcessingTargetId
from ...domain.scopes import RequestedScope
from .datasets import DatasetBindings, ParameterBinding
from .policies import AlignmentPolicy, BoundaryPolicy, NormalizationPolicy


@dataclass(frozen=True, slots=True)
class ProcessingRequest:
    compiled_plan: CompiledPlanId
    datasets: DatasetBindings
    parameters: ParameterBinding
    targets: tuple[ProcessingTargetId, ...]
    scope: RequestedScope
    boundary_policy: BoundaryPolicy
    alignment_policy: AlignmentPolicy
    normalization_policy: NormalizationPolicy

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("A processing request requires at least one target.")
        if len(self.targets) != len(set(self.targets)):
            raise ValueError("Processing request targets must be unique.")
