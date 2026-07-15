"""Authoritative execution report and explicit process-outcome contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ...domain.failures import FailureCategory, FailureDetail
from ...domain.identifiers import (
    CalculationNodeId,
    CompiledPlanId,
    DatasetRole,
    ExecutionInstanceId,
    OccurrenceId,
    ProcessingTargetId,
    ScopeId,
)
from ...domain.results import ArtifactResult, NodeStatus
from ...domain.scopes import RequestedScope, ResolvedScope
from .datasets import DatasetBindings


class ReportStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ResultRecord:
    node_id: CalculationNodeId
    execution_instance: ExecutionInstanceId
    target_id: ProcessingTargetId
    dataset_role: DatasetRole
    scope: ScopeId
    occurrence: OccurrenceId | None
    scope_ancestry: tuple[ScopeId, ...]
    artifact: ArtifactResult

    def __post_init__(self) -> None:
        if not self.scope_ancestry or self.scope_ancestry[-1] != self.scope:
            raise ValueError("A result must retain ancestry ending in its execution scope.")
        if len(self.scope_ancestry) != len(set(self.scope_ancestry)):
            raise ValueError("A result scope ancestry cannot repeat a scope ID.")
        if self.occurrence is not None and len(self.scope_ancestry) < 2:
            raise ValueError("An occurrence result must retain its parent scope.")
        provenance = self.artifact.provenance
        if provenance is not None and provenance.node_id != self.node_id:
            raise ValueError("Result provenance must identify the record's node.")


@dataclass(frozen=True, slots=True)
class ExecutionInstanceStatusRecord:
    execution_instance: ExecutionInstanceId
    node_id: CalculationNodeId
    scope: ScopeId
    occurrence: OccurrenceId | None
    status: NodeStatus
    failure: FailureDetail | None = None

    def __post_init__(self) -> None:
        if self.status is NodeStatus.SUCCEEDED:
            if self.failure is not None:
                raise ValueError("A succeeded execution instance cannot carry a failure.")
            return
        if self.failure is None:
            raise ValueError("A failed or skipped execution instance requires a failure.")
        if self.failure.category is not FailureCategory.NODE:
            raise ValueError("An execution instance requires a node-level failure.")


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    compiled_plan: CompiledPlanId
    datasets: DatasetBindings
    requested_scope: RequestedScope
    resolved_scope: ResolvedScope
    status: ReportStatus
    results: tuple[ResultRecord, ...]
    instances: tuple[ExecutionInstanceStatusRecord, ...]

    def __post_init__(self) -> None:
        if self.resolved_scope.requested != self.requested_scope:
            raise ValueError("The resolved scope must belong to the reported request scope.")
        if not self.instances:
            raise ValueError("An execution report requires instance status records.")

        instance_by_id = {
            instance.execution_instance: instance
            for instance in self.instances
        }
        if len(instance_by_id) != len(self.instances):
            raise ValueError("Execution instance IDs must be unique in a report.")

        dataset_roles = {binding.role for binding in self.datasets.values}
        report_ancestry = self.resolved_scope.ancestry
        for result in self.results:
            if result.scope_ancestry[: len(report_ancestry)] != report_ancestry:
                raise ValueError("A result scope must descend from the resolved request scope.")
            if result.dataset_role not in dataset_roles:
                raise ValueError("A result must reference a bound dataset role.")
            try:
                instance = instance_by_id[result.execution_instance]
            except KeyError as error:
                raise ValueError(
                    "A result must reference a reported execution instance."
                ) from error
            if (
                instance.node_id != result.node_id
                or instance.scope != result.scope
                or instance.occurrence != result.occurrence
                or instance.status is not result.artifact.status
            ):
                raise ValueError("A result must agree with its execution instance status.")

        expected_status = _derive_report_status(self.instances)
        if self.status is not expected_status:
            raise ValueError(
                f"Instance statuses require report status {expected_status.value}."
            )


@dataclass(frozen=True, slots=True)
class RequestRejected:
    failures: tuple[FailureDetail, ...]

    def __post_init__(self) -> None:
        if not self.failures:
            raise ValueError("A rejected request requires at least one failure.")
        if any(
            failure.category is not FailureCategory.REQUEST
            for failure in self.failures
        ):
            raise ValueError("Request rejection accepts only request-level failures.")


@dataclass(frozen=True, slots=True)
class ExecutionCompleted:
    report: ExecutionReport


ProcessOutcome: TypeAlias = RequestRejected | ExecutionCompleted


def _derive_report_status(
    instances: tuple[ExecutionInstanceStatusRecord, ...],
) -> ReportStatus:
    succeeded = sum(
        instance.status is NodeStatus.SUCCEEDED
        for instance in instances
    )
    if succeeded == len(instances):
        return ReportStatus.SUCCESS
    if succeeded:
        return ReportStatus.PARTIAL_SUCCESS
    return ReportStatus.FAILED
