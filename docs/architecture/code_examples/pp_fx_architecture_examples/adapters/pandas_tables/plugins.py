"""Node-local pandas preparation and explicit table-artifact return boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from ...application.contracts.datasets import ParameterSet
from ...application.contracts.operations import (
    PluginExecutionResult,
    PreparedNodeInput,
    ProducedTableArtifact,
)
from ...application.contracts.plans import CompiledNodeSpec
from ...domain.identifiers import DatasetRole
from ...domain.scopes import ResolvedScope
from .processing import PandasRoleTable
from .workspace import TableWorkspace


@dataclass(frozen=True, slots=True)
class PandasNodeInput:
    """Adapter-local prepared value; every frame is isolated from the workspace."""

    frame: pd.DataFrame
    datasets: tuple[PandasRoleTable, ...]
    parameters: ParameterSet
    scope: ResolvedScope

    def __post_init__(self) -> None:
        roles = tuple(dataset.role for dataset in self.datasets)
        if roles.count(DatasetRole("primary")) != 1:
            raise ValueError("Pandas node input requires exactly one primary frame.")
        if len(roles) != len(set(roles)):
            raise ValueError("Pandas node input dataset roles must be unique.")


class PandasNodeInvoker(Protocol):
    """Seam for callable lookup and public plugin-DTO mapping."""

    def invoke(
        self,
        node: CompiledNodeSpec,
        data: PandasNodeInput,
    ) -> pd.DataFrame: ...


class PandasPluginExecutor:
    """Illustrative table-producing executor; no callable lookup lives here."""

    def __init__(
        self,
        workspace: TableWorkspace,
        invoker: PandasNodeInvoker,
    ) -> None:
        self._workspace = workspace
        self._invoker = invoker

    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult:
        if len(node.produces) != 1:
            raise ValueError("The table executor example requires exactly one output.")

        local_datasets = tuple(
            PandasRoleTable(
                role=dataset.role,
                table=self._workspace.isolate(dataset.table),
            )
            for dataset in data.datasets
        )
        primary = next(
            dataset.table
            for dataset in local_datasets
            if dataset.role == DatasetRole("primary")
        )
        invocation = PandasNodeInput(
            frame=primary,
            datasets=local_datasets,
            parameters=data.parameters,
            scope=data.scope,
        )
        returned_frame = self._invoker.invoke(node, invocation)
        if not isinstance(returned_frame, pd.DataFrame):
            raise TypeError("A table-producing plugin must return a pandas DataFrame.")

        artifact_id = node.produces[0]
        artifact_handle = self._workspace.store(
            returned_frame.copy(deep=True),
            label=f"artifact-{artifact_id.value}",
        )
        return PluginExecutionResult(
            node_id=node.id,
            scalar_results=(),
            table_artifacts=(
                ProducedTableArtifact(
                    id=artifact_id,
                    table=artifact_handle,
                ),
            ),
        )
