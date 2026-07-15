"""In-memory pandas dataset gateway at the application boundary."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...application.contracts.datasets import (
    DatasetBinding,
    DatasetFingerprint,
    LoadedDataset,
)
from .workspace import TableWorkspace


@dataclass(frozen=True, slots=True)
class PandasDatasetSource:
    """Adapter registration value; its DataFrame never crosses inward."""

    binding: DatasetBinding
    frame: pd.DataFrame
    fingerprint: DatasetFingerprint


class InMemoryPandasDatasetGateway:
    def __init__(
        self,
        workspace: TableWorkspace,
        *,
        sources: tuple[PandasDatasetSource, ...],
    ) -> None:
        bindings = tuple(source.binding for source in sources)
        if len(bindings) != len(set(bindings)):
            raise ValueError("Pandas dataset source bindings must be unique.")
        self._workspace = workspace
        self._sources = sources

    def load(self, binding: DatasetBinding) -> LoadedDataset:
        source = self._find_source(binding)
        canonical_frame = source.frame.copy(deep=True)
        handle = self._workspace.store(
            canonical_frame,
            label=f"dataset-{binding.role.value}-{binding.dataset.value}",
        )
        return LoadedDataset(
            binding=binding,
            table=handle,
            fingerprint=source.fingerprint,
        )

    def _find_source(self, binding: DatasetBinding) -> PandasDatasetSource:
        for source in self._sources:
            if source.binding == binding:
                return source
        raise KeyError(binding)
