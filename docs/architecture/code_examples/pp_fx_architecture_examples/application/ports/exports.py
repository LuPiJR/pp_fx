"""Report-export capability kept separate from calculation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts.exports import ExportOutcome, ExportRequest


@runtime_checkable
class ReportExporter(Protocol):
    def export(self, request: ExportRequest) -> ExportOutcome: ...
