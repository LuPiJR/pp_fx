"""Thin Python driving adapter over the shared ProcessDataset input port."""

from __future__ import annotations

from ..application.contracts.reports import ProcessOutcome
from ..application.ports.use_cases import ProcessDataset
from .request_dtos import PythonProcessInput
from .request_mapping import PythonRequestBuilder


class PythonProcessingFacade:
    def __init__(
        self,
        request_builder: PythonRequestBuilder,
        processor: ProcessDataset,
    ) -> None:
        self._request_builder = request_builder
        self._processor = processor

    def process(self, request: PythonProcessInput) -> ProcessOutcome:
        application_request = self._request_builder.build(request)
        return self._processor.execute(application_request)
