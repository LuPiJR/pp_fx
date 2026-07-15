"""Focused tabular-processing capabilities without pandas annotations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts.operations import (
    AlignedDatasets,
    ContextExpansionRequest,
    ContextExpansionResult,
    DatasetAlignmentRequest,
    NormalizationRequest,
    NormalizationResult,
    ScopeResolutionRequest,
    ScopeResolutionResult,
)


@runtime_checkable
class ScopeResolver(Protocol):
    def resolve(self, request: ScopeResolutionRequest) -> ScopeResolutionResult: ...


@runtime_checkable
class DatasetNormalizer(Protocol):
    def normalize(self, request: NormalizationRequest) -> NormalizationResult: ...


@runtime_checkable
class ContextExpander(Protocol):
    def expand(self, request: ContextExpansionRequest) -> ContextExpansionResult: ...


@runtime_checkable
class DatasetAligner(Protocol):
    def align(self, request: DatasetAlignmentRequest) -> AlignedDatasets: ...
