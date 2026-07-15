"""Calculation-independent report export request and outcome values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from .reports import ExecutionReport

_EXPORT_FAILURE_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class ExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


@dataclass(frozen=True, slots=True)
class PresentationUnitProfileId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value != self.value.strip():
            raise ValueError("A presentation-unit profile ID is required.")


@dataclass(frozen=True, slots=True)
class ExportDestination:
    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value != self.value.strip():
            raise ValueError("An export destination reference is required.")


@dataclass(frozen=True, slots=True)
class ExportRequest:
    report: ExecutionReport
    format: ExportFormat
    presentation_units: PresentationUnitProfileId
    destination: ExportDestination


@dataclass(frozen=True, slots=True)
class ExportReceipt:
    destination: ExportDestination
    artifact_count: int

    def __post_init__(self) -> None:
        if self.artifact_count < 0:
            raise ValueError("An export artifact count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ExportFailed:
    code: str
    message: str

    def __post_init__(self) -> None:
        if not _EXPORT_FAILURE_CODE.fullmatch(self.code):
            raise ValueError("An export failure code must be uppercase snake case.")
        if not self.message or self.message != self.message.strip():
            raise ValueError("An export failure message is required.")


ExportOutcome: TypeAlias = ExportReceipt | ExportFailed
