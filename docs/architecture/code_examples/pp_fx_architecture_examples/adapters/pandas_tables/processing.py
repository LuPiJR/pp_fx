"""Pandas scope/alignment boundaries that resolve application handles internally."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

import pandas as pd

from ...application.contracts.operations import (
    AlignedDatasets,
    AlignmentReport,
    DatasetAlignmentRequest,
    RoleTable,
    ScopeResolutionRequest,
    ScopeResolutionResult,
)
from ...domain.identifiers import DatasetRole
from ...domain.scopes import ResolvedScope
from .workspace import TableWorkspace


@dataclass(frozen=True, slots=True)
class PandasRoleTable:
    role: DatasetRole
    table: pd.DataFrame


class ScopeFrameKernel(Protocol):
    """Tabular policy implementation injected into the handle-resolving adapter."""

    def resolve(
        self,
        table: pd.DataFrame,
        request: ScopeResolutionRequest,
    ) -> tuple[pd.DataFrame, ResolvedScope]: ...


class AlignmentFrameKernel(Protocol):
    """Alignment algorithm seam; this slice deliberately supplies no algorithm."""

    def align(
        self,
        primary: pd.DataFrame,
        comparisons: tuple[PandasRoleTable, ...],
        request: DatasetAlignmentRequest,
    ) -> tuple[tuple[PandasRoleTable, ...], AlignmentReport]: ...


class WorkspaceScopeResolver:
    def __init__(
        self,
        workspace: TableWorkspace,
        kernel: ScopeFrameKernel,
    ) -> None:
        self._workspace = workspace
        self._kernel = kernel

    def resolve(self, request: ScopeResolutionRequest) -> ScopeResolutionResult:
        canonical = self._workspace.resolve(request.dataset.table)
        scoped_frame, resolved_scope = self._kernel.resolve(canonical, request)
        scoped_handle = self._workspace.store(
            scoped_frame.copy(deep=True),
            label=f"scope-{resolved_scope.requested.id.value}",
        )
        return ScopeResolutionResult(
            dataset=replace(request.dataset, table=scoped_handle),
            scope=resolved_scope,
        )


class WorkspaceDatasetAligner:
    def __init__(
        self,
        workspace: TableWorkspace,
        kernel: AlignmentFrameKernel,
    ) -> None:
        self._workspace = workspace
        self._kernel = kernel

    def align(self, request: DatasetAlignmentRequest) -> AlignedDatasets:
        primary = self._workspace.resolve(request.primary.dataset.table)
        comparisons = tuple(
            PandasRoleTable(
                role=dataset.binding.role,
                table=self._workspace.resolve(dataset.table),
            )
            for dataset in request.comparisons
        )
        aligned_frames, report = self._kernel.align(
            primary,
            comparisons,
            request,
        )
        role_tables = tuple(
            RoleTable(
                role=item.role,
                table=self._workspace.store(
                    item.table.copy(deep=True),
                    label=f"aligned-{item.role.value}",
                ),
            )
            for item in aligned_frames
        )
        return AlignedDatasets(values=role_tables, report=report)
