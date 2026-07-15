"""Framework-free external request shapes owned by delivery adapters."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PythonDatasetInput:
    role: str
    reference: str
    ingestion_profile: str


@dataclass(frozen=True, slots=True)
class PythonParameterInput:
    reference: str
    ingestion_profile: str | None = None


@dataclass(frozen=True, slots=True)
class PythonScopeInput:
    id: str
    axis: str
    start: Decimal
    end: Decimal
    unit: str


@dataclass(frozen=True, slots=True)
class PythonProcessInput:
    compiled_plan: str
    datasets: tuple[PythonDatasetInput, ...]
    parameters: PythonParameterInput
    targets: tuple[str, ...]
    scope: PythonScopeInput
    boundary_mode: str
    out_of_range: str
    alignment: str
    normalization: str


@dataclass(frozen=True, slots=True)
class JsonDatasetBindingV1:
    role: str
    reference: str
    ingestion_profile: str


@dataclass(frozen=True, slots=True)
class JsonParameterBindingV1:
    reference: str
    ingestion_profile: str | None = None


@dataclass(frozen=True, slots=True)
class JsonQuantityV1:
    magnitude: str
    unit: str


@dataclass(frozen=True, slots=True)
class JsonScopeV1:
    id: str
    axis: str
    start: JsonQuantityV1
    end: JsonQuantityV1


@dataclass(frozen=True, slots=True)
class JsonBoundaryPolicyV1:
    mode: str
    out_of_range: str


@dataclass(frozen=True, slots=True)
class JsonProcessRequestV1:
    schema_version: str
    compiled_plan: str
    datasets: tuple[JsonDatasetBindingV1, ...]
    parameters: JsonParameterBindingV1
    targets: tuple[str, ...]
    scope: JsonScopeV1
    boundary_policy: JsonBoundaryPolicyV1
    alignment_policy: str
    normalization_policy: str
