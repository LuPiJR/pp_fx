"""Driving input-port contracts implemented by application services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts.exports import ExportOutcome, ExportRequest
from ..contracts.reports import ProcessOutcome
from ..contracts.requests import ProcessingRequest


@runtime_checkable
class ProcessDataset(Protocol):
    def execute(self, request: ProcessingRequest) -> ProcessOutcome: ...


@runtime_checkable
class ExportReport(Protocol):
    def execute(self, request: ExportRequest) -> ExportOutcome: ...
