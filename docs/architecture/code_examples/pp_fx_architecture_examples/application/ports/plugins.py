"""Application-owned plugin execution capability."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts.operations import PluginExecutionResult, PreparedNodeInput
from ..contracts.plans import CompiledNodeSpec


@runtime_checkable
class PluginExecutionPort(Protocol):
    def execute(
        self,
        node: CompiledNodeSpec,
        data: PreparedNodeInput,
    ) -> PluginExecutionResult: ...
