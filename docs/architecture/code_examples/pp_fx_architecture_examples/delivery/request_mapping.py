"""Explicit Python/JSON mapping into one application request contract."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DecimalException
from typing import Callable, Protocol, TypeVar

from ..application.contracts.datasets import (
    DatasetBinding,
    DatasetBindings,
    ParameterBinding,
)
from ..application.contracts.policies import (
    AlignmentPolicy,
    BoundaryPolicy,
    NormalizationPolicy,
    OutOfRangeMode,
)
from ..application.contracts.requests import ProcessingRequest
from ..domain.identifiers import (
    CompiledPlanId,
    DatasetReference,
    DatasetRole,
    IngestionProfileReference,
    ParameterSetReference,
    ProcessingTargetId,
    ScopeId,
)
from ..domain.scopes import BoundaryMode, CoordinateAxis, RequestedScope
from ..domain.units import Quantity, Unit
from .request_dtos import (
    JsonProcessRequestV1,
    PythonProcessInput,
)

T = TypeVar("T")
GrpcMessageT = TypeVar("GrpcMessageT", contravariant=True)


class DeliveryMappingError(ValueError):
    def __init__(self, path: str, code: str, message: str) -> None:
        self.path = path
        self.code = code
        self.detail = message
        super().__init__(f"{path}: {message}")


class RequestValueCatalog(Protocol):
    def resolve_axis(self, reference: str) -> CoordinateAxis | None: ...

    def resolve_unit(self, reference: str) -> Unit | None: ...


class FutureGrpcRequestMapper(Protocol[GrpcMessageT]):
    """Signature for a future generated-protobuf anti-corruption mapper."""

    def to_application(self, message: GrpcMessageT) -> ProcessingRequest: ...


@dataclass(frozen=True, slots=True)
class _DatasetValues:
    role: str
    reference: str
    ingestion_profile: str


@dataclass(frozen=True, slots=True)
class _ParameterValues:
    reference: str
    ingestion_profile: str | None


@dataclass(frozen=True, slots=True)
class _ScopeValues:
    id: str
    axis: str
    start: Decimal
    start_unit: str
    end: Decimal
    end_unit: str


@dataclass(frozen=True, slots=True)
class _RequestValues:
    compiled_plan: str
    datasets: tuple[_DatasetValues, ...]
    parameters: _ParameterValues
    targets: tuple[str, ...]
    scope: _ScopeValues
    boundary_mode: str
    out_of_range: str
    alignment: str
    normalization: str


class PythonRequestBuilder:
    def __init__(self, catalog: RequestValueCatalog) -> None:
        self._mapper = _ApplicationRequestMapper(catalog)

    def build(self, request: PythonProcessInput) -> ProcessingRequest:
        scope = request.scope
        return self._mapper.map(
            _RequestValues(
                compiled_plan=request.compiled_plan,
                datasets=tuple(
                    _DatasetValues(
                        item.role,
                        item.reference,
                        item.ingestion_profile,
                    )
                    for item in request.datasets
                ),
                parameters=_ParameterValues(
                    request.parameters.reference,
                    request.parameters.ingestion_profile,
                ),
                targets=request.targets,
                scope=_ScopeValues(
                    scope.id,
                    scope.axis,
                    _require_decimal(scope.start, "scope.start"),
                    scope.unit,
                    _require_decimal(scope.end, "scope.end"),
                    scope.unit,
                ),
                boundary_mode=request.boundary_mode,
                out_of_range=request.out_of_range,
                alignment=request.alignment,
                normalization=request.normalization,
            )
        )


class JsonRequestMapperV1:
    SCHEMA_VERSION = "pp-fx.process-request/v1"

    def __init__(self, catalog: RequestValueCatalog) -> None:
        self._mapper = _ApplicationRequestMapper(catalog)

    def map(self, request: JsonProcessRequestV1) -> ProcessingRequest:
        if request.schema_version != self.SCHEMA_VERSION:
            raise DeliveryMappingError(
                "schema_version",
                "UNSUPPORTED_SCHEMA_VERSION",
                f"Expected {self.SCHEMA_VERSION}.",
            )
        scope = request.scope
        return self._mapper.map(
            _RequestValues(
                compiled_plan=request.compiled_plan,
                datasets=tuple(
                    _DatasetValues(
                        item.role,
                        item.reference,
                        item.ingestion_profile,
                    )
                    for item in request.datasets
                ),
                parameters=_ParameterValues(
                    request.parameters.reference,
                    request.parameters.ingestion_profile,
                ),
                targets=request.targets,
                scope=_ScopeValues(
                    scope.id,
                    scope.axis,
                    _parse_decimal(scope.start.magnitude, "scope.start.magnitude"),
                    scope.start.unit,
                    _parse_decimal(scope.end.magnitude, "scope.end.magnitude"),
                    scope.end.unit,
                ),
                boundary_mode=request.boundary_policy.mode,
                out_of_range=request.boundary_policy.out_of_range,
                alignment=request.alignment_policy,
                normalization=request.normalization_policy,
            )
        )


class _ApplicationRequestMapper:
    def __init__(self, catalog: RequestValueCatalog) -> None:
        self._catalog = catalog

    def map(self, values: _RequestValues) -> ProcessingRequest:
        scope = self._scope(values.scope)
        datasets = self._datasets(values.datasets)
        parameters = self._parameters(values.parameters)
        targets = tuple(
            _parse(ProcessingTargetId, value, f"targets[{index}]")
            for index, value in enumerate(values.targets)
        )
        try:
            return ProcessingRequest(
                compiled_plan=_parse(
                    CompiledPlanId,
                    values.compiled_plan,
                    "compiled_plan",
                ),
                datasets=datasets,
                parameters=parameters,
                targets=targets,
                scope=scope,
                boundary_policy=BoundaryPolicy(
                    _parse(BoundaryMode, values.boundary_mode, "boundary_mode"),
                    _parse(OutOfRangeMode, values.out_of_range, "out_of_range"),
                ),
                alignment_policy=_parse(
                    AlignmentPolicy,
                    values.alignment,
                    "alignment",
                ),
                normalization_policy=_parse(
                    NormalizationPolicy,
                    values.normalization,
                    "normalization",
                ),
            )
        except DeliveryMappingError:
            raise
        except (TypeError, ValueError) as error:
            raise DeliveryMappingError(
                "request",
                "INVALID_REQUEST",
                str(error),
            ) from error

    def _datasets(
        self,
        values: tuple[_DatasetValues, ...],
    ) -> DatasetBindings:
        bindings = tuple(
            DatasetBinding(
                role=_parse(DatasetRole, item.role, f"datasets[{index}].role"),
                dataset=_parse(
                    DatasetReference,
                    item.reference,
                    f"datasets[{index}].reference",
                ),
                ingestion_profile=_parse(
                    IngestionProfileReference,
                    item.ingestion_profile,
                    f"datasets[{index}].ingestion_profile",
                ),
            )
            for index, item in enumerate(values)
        )
        try:
            return DatasetBindings(bindings)
        except ValueError as error:
            raise DeliveryMappingError(
                "datasets",
                "INVALID_DATASET_BINDINGS",
                str(error),
            ) from error

    @staticmethod
    def _parameters(values: _ParameterValues) -> ParameterBinding:
        ingestion = (
            None
            if values.ingestion_profile is None
            else _parse(
                IngestionProfileReference,
                values.ingestion_profile,
                "parameters.ingestion_profile",
            )
        )
        return ParameterBinding(
            parameter_set=_parse(
                ParameterSetReference,
                values.reference,
                "parameters.reference",
            ),
            ingestion_profile=ingestion,
        )

    def _scope(self, values: _ScopeValues) -> RequestedScope:
        axis = self._catalog.resolve_axis(values.axis)
        if axis is None:
            raise DeliveryMappingError(
                "scope.axis",
                "UNKNOWN_AXIS",
                f"Unknown coordinate axis {values.axis!r}.",
            )
        start = self._quantity(
            values.start,
            values.start_unit,
            axis,
            "scope.start",
        )
        end = self._quantity(
            values.end,
            values.end_unit,
            axis,
            "scope.end",
        )
        try:
            return RequestedScope(
                id=_parse(ScopeId, values.id, "scope.id"),
                axis=axis,
                start=start,
                end=end,
            )
        except DeliveryMappingError:
            raise
        except (TypeError, ValueError) as error:
            raise DeliveryMappingError(
                "scope",
                "INVALID_SCOPE",
                str(error),
            ) from error

    def _quantity(
        self,
        magnitude: Decimal,
        unit_reference: str,
        axis: CoordinateAxis,
        path: str,
    ) -> Quantity:
        unit = self._catalog.resolve_unit(unit_reference)
        if unit is None:
            raise DeliveryMappingError(
                f"{path}.unit",
                "UNKNOWN_UNIT",
                f"Unknown unit {unit_reference!r}.",
            )
        if unit.quantity_kind != axis.quantity_kind:
            raise DeliveryMappingError(
                f"{path}.unit",
                "INCOMPATIBLE_UNIT",
                f"Unit {unit_reference!r} is incompatible with axis {axis.id.value}.",
            )
        try:
            return Quantity(magnitude, unit)
        except (TypeError, ValueError) as error:
            raise DeliveryMappingError(path, "INVALID_QUANTITY", str(error)) from error


def _parse(factory: Callable[[str], T], value: str, path: str) -> T:
    try:
        return factory(value)
    except (TypeError, ValueError) as error:
        raise DeliveryMappingError(path, "INVALID_VALUE", str(error)) from error


def _parse_decimal(value: str, path: str) -> Decimal:
    try:
        return Decimal(value)
    except (DecimalException, TypeError, ValueError) as error:
        raise DeliveryMappingError(
            path,
            "INVALID_DECIMAL",
            "Expected a finite decimal string.",
        ) from error


def _require_decimal(value: Decimal, path: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise DeliveryMappingError(
            path,
            "INVALID_DECIMAL",
            "Expected Decimal at the Python facade boundary.",
        )
    return value
