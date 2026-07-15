"""Calculation-independent report-export use case."""

from __future__ import annotations

from ..contracts.exports import ExportOutcome, ExportRequest
from ..ports.exports import ReportExporter


class ExportReportService:
    def __init__(self, exporter: ReportExporter) -> None:
        self._exporter = exporter

    def execute(self, request: ExportRequest) -> ExportOutcome:
        return self._exporter.export(request)
