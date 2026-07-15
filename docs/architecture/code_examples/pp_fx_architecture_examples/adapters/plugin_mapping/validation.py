"""Explicit static validation values returned by declaration mapping."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...application.contracts.plans import CompiledNodeSpec


class MappingFailureCode(StrEnum):
    UNKNOWN_CHANNEL = "unknown_channel"
    UNKNOWN_PARAMETER = "unknown_parameter"
    UNKNOWN_QUANTITY = "unknown_quantity"
    UNKNOWN_UNIT = "unknown_unit"
    INCOMPATIBLE_DIMENSION = "incompatible_dimension"
    UNIT_QUANTITY_MISMATCH = "unit_quantity_mismatch"
    INVALID_IDENTIFIER = "invalid_identifier"
    INVALID_DECLARATION = "invalid_declaration"


@dataclass(frozen=True, slots=True)
class MappingFailure:
    code: MappingFailureCode
    reference: str
    message: str

    def __post_init__(self) -> None:
        if not self.reference or not self.message:
            raise ValueError("A mapping failure requires reference and message details.")


@dataclass(frozen=True, slots=True)
class StaticValidationResult:
    failures: tuple[MappingFailure, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.failures


@dataclass(frozen=True, slots=True)
class NodeMappingResult:
    specification: CompiledNodeSpec | None
    validation: StaticValidationResult

    def __post_init__(self) -> None:
        if self.validation.is_valid != (self.specification is not None):
            raise ValueError(
                "A valid mapping requires a specification; an invalid mapping forbids one."
            )
