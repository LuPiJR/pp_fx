"""Dataset and parameter values crossing application port boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

from ...domain.identifiers import (
    DatasetReference,
    DatasetRole,
    IngestionProfileReference,
    ParameterId,
    ParameterSetReference,
)
from ...domain.units import Quantity
from .tables import TableHandle

_FINGERPRINT = re.compile(r"^[a-z][a-z0-9]*:[0-9a-f]+$")
ParameterValue: TypeAlias = Quantity | bool | str


@dataclass(frozen=True, slots=True)
class DatasetBinding:
    role: DatasetRole
    dataset: DatasetReference
    ingestion_profile: IngestionProfileReference


@dataclass(frozen=True, slots=True)
class DatasetBindings:
    values: tuple[DatasetBinding, ...]

    def __post_init__(self) -> None:
        roles = tuple(binding.role for binding in self.values)
        if len(roles) != len(set(roles)):
            raise ValueError("Dataset binding roles must be unique.")
        if roles.count(DatasetRole("primary")) != 1:
            raise ValueError("Dataset bindings require exactly one primary role.")

    @property
    def primary(self) -> DatasetBinding:
        return next(
            binding
            for binding in self.values
            if binding.role == DatasetRole("primary")
        )


@dataclass(frozen=True, slots=True)
class DatasetFingerprint:
    value: str

    def __post_init__(self) -> None:
        if not _FINGERPRINT.fullmatch(self.value):
            raise ValueError("A dataset fingerprint requires an algorithm and hex digest.")


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    """Adapter-loaded data represented only by metadata and an opaque handle."""

    binding: DatasetBinding
    table: TableHandle
    fingerprint: DatasetFingerprint


@dataclass(frozen=True, slots=True)
class ParameterBinding:
    parameter_set: ParameterSetReference
    ingestion_profile: IngestionProfileReference | None = None


@dataclass(frozen=True, slots=True)
class ParameterEntry:
    id: ParameterId
    value: ParameterValue

    def __post_init__(self) -> None:
        if isinstance(self.value, str) and not self.value:
            raise ValueError("A textual parameter value cannot be empty.")
        if not isinstance(self.value, (Quantity, bool, str)):
            raise TypeError("A numeric parameter must be a typed Quantity.")


@dataclass(frozen=True, slots=True)
class ParameterSet:
    """Application-owned immutable parameter values returned by a gateway."""

    reference: ParameterSetReference
    values: tuple[ParameterEntry, ...]

    def __post_init__(self) -> None:
        parameter_ids = tuple(entry.id for entry in self.values)
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("Parameter IDs must be unique within a parameter set.")
