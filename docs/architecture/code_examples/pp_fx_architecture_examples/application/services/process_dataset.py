"""Sequential ProcessDataset orchestration over injected application ports."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.failures import FailureCategory, FailureDetail
from ...domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    DatasetRole,
    ExecutionInstanceId,
    ProcessingTargetId,
)
from ...domain.results import ArtifactResult, NodeStatus
from ...domain.scopes import ResolvedScope
from ..contracts.datasets import LoadedDataset, ParameterSet
from ..contracts.operations import (
    AlignedDatasets,
    ContextExpansionRequest,
    ContextExpansionResult,
    ContextRequirementSpec,
    DatasetAlignmentRequest,
    NormalizationRequest,
    PluginExecutionResult,
    PreparedNodeInput,
    ProducedTableArtifact,
    ScopeResolutionRequest,
)
from ..contracts.plans import CompiledNodeSpec, CompiledPlan, TargetClosure
from ..contracts.reports import (
    ExecutionCompleted,
    ExecutionInstanceStatusRecord,
    ExecutionReport,
    ProcessOutcome,
    ReportStatus,
    RequestRejected,
    ResultRecord,
)
from ..contracts.requests import ProcessingRequest
from ..ports.gateways import CompiledPlanRepository, DatasetGateway, ParameterGateway
from ..ports.plugins import PluginExecutionPort
from ..ports.processing import (
    ContextExpander,
    DatasetAligner,
    DatasetNormalizer,
    ScopeResolver,
)
from .graph_compiler import select_target_closure


@dataclass(frozen=True, slots=True)
class _PreparedRequest:
    datasets: AlignedDatasets
    parameters: ParameterSet
    scope: ResolvedScope


class ProcessDatasetService:
    """Educational same-scope scheduler; every technology choice is injected."""

    def __init__(
        self,
        *,
        plans: CompiledPlanRepository,
        datasets: DatasetGateway,
        parameters: ParameterGateway,
        normalizer: DatasetNormalizer,
        scopes: ScopeResolver,
        contexts: ContextExpander,
        aligner: DatasetAligner,
        plugins: PluginExecutionPort,
    ) -> None:
        self._plans = plans
        self._datasets = datasets
        self._parameters = parameters
        self._normalizer = normalizer
        self._scopes = scopes
        self._contexts = contexts
        self._aligner = aligner
        self._plugins = plugins

    def execute(self, request: ProcessingRequest) -> ProcessOutcome:
        plan = self._plans.get(request.compiled_plan)
        failures = self._target_failures(plan, request.targets)
        if failures:
            return RequestRejected(failures)

        closure = select_target_closure(plan.graph, request.targets)
        failures = self._required_role_failures(plan, closure, request)
        if failures:
            return RequestRejected(failures)

        prepared = self._prepare_request(plan, closure, request)
        instances, results = self._execute_closure(plan, closure, prepared)
        report = ExecutionReport(
            compiled_plan=plan.id,
            datasets=request.datasets,
            requested_scope=request.scope,
            resolved_scope=prepared.scope,
            status=self._report_status(instances),
            results=results,
            instances=instances,
        )
        return ExecutionCompleted(report)

    def _prepare_request(
        self,
        plan: CompiledPlan,
        closure: TargetClosure,
        request: ProcessingRequest,
    ) -> _PreparedRequest:
        loaded = tuple(
            self._datasets.load(binding) for binding in request.datasets.values
        )
        parameters = self._parameters.load(request.parameters)
        normalized = tuple(
            self._normalizer.normalize(
                NormalizationRequest(dataset, request.normalization_policy)
            ).dataset
            for dataset in loaded
        )
        primary = next(
            dataset
            for dataset in normalized
            if dataset.binding.role == DatasetRole("primary")
        )
        scoped = self._scopes.resolve(
            ScopeResolutionRequest(
                dataset=primary,
                scope=request.scope,
                boundary_policy=request.boundary_policy,
            )
        )
        expanded = self._contexts.expand(
            ContextExpansionRequest(
                dataset=scoped.dataset,
                scope=scoped.scope,
                requirement=self._context_requirement(plan, closure),
            )
        )
        comparisons = tuple(
            dataset
            for dataset in normalized
            if dataset.binding.role != DatasetRole("primary")
        )
        if expanded.target_scope != scoped.scope:
            raise RuntimeError("Context expansion changed the resolved target scope.")
        aligned = self._aligner.align(
            DatasetAlignmentRequest(
                primary=expanded,
                comparisons=comparisons,
                policy=request.alignment_policy,
            )
        )
        self._validate_aligned_roles(aligned, request)
        return _PreparedRequest(aligned, parameters, expanded.target_scope)

    def _execute_closure(
        self,
        plan: CompiledPlan,
        closure: TargetClosure,
        prepared: _PreparedRequest,
    ) -> tuple[tuple[ExecutionInstanceStatusRecord, ...], tuple[ResultRecord, ...]]:
        nodes = {node.id: node for node in plan.nodes}
        predecessors = self._predecessors(closure)
        statuses: dict[CalculationNodeId, NodeStatus] = {}
        scalar_artifacts: dict[ArtifactId, ArtifactResult] = {}
        table_artifacts: dict[ArtifactId, ProducedTableArtifact] = {}
        instances: list[ExecutionInstanceStatusRecord] = []
        results: list[ResultRecord] = []

        for node_id in closure.node_ids:
            node = nodes[node_id]
            blocked_by = next(
                (
                    predecessor
                    for predecessor in predecessors[node_id]
                    if statuses[predecessor] is not NodeStatus.SUCCEEDED
                ),
                None,
            )
            if blocked_by is not None:
                failure = FailureDetail(
                    FailureCategory.NODE,
                    "DEPENDENCY_FAILED",
                    f"Blocked by failed dependency {blocked_by.value}.",
                )
                statuses[node_id] = NodeStatus.NOT_CALCULATED
                instances.append(
                    self._instance_record(
                        node,
                        prepared.scope,
                        NodeStatus.NOT_CALCULATED,
                        failure,
                    )
                )
                continue

            execution = self._plugins.execute(
                node,
                PreparedNodeInput(
                    datasets=prepared.datasets.values,
                    parameters=prepared.parameters,
                    scope=prepared.scope,
                    scalar_artifacts=tuple(
                        scalar_artifacts[artifact]
                        for artifact in node.consumes
                        if artifact in scalar_artifacts
                    ),
                    table_artifacts=tuple(
                        table_artifacts[artifact]
                        for artifact in node.consumes
                        if artifact in table_artifacts
                    ),
                ),
            )
            status, failure = self._validate_execution(node, execution)
            statuses[node_id] = status
            instances.append(
                self._instance_record(node, prepared.scope, status, failure)
            )
            results.extend(
                self._result_records(
                    plan,
                    closure,
                    node,
                    prepared.scope,
                    execution.scalar_results,
                )
            )
            if status is NodeStatus.SUCCEEDED:
                scalar_artifacts.update(
                    (artifact.artifact_id, artifact)
                    for artifact in execution.scalar_results
                )
                table_artifacts.update(
                    (artifact.id, artifact)
                    for artifact in execution.table_artifacts
                )

        return tuple(instances), tuple(results)

    @staticmethod
    def _target_failures(
        plan: CompiledPlan,
        target_ids: tuple[ProcessingTargetId, ...],
    ) -> tuple[FailureDetail, ...]:
        known = {target.id for target in plan.targets}
        return tuple(
            FailureDetail(
                FailureCategory.REQUEST,
                "UNKNOWN_TARGET",
                f"Unknown processing target {target_id.value}.",
            )
            for target_id in target_ids
            if target_id not in known
        )

    @staticmethod
    def _required_role_failures(
        plan: CompiledPlan,
        closure: TargetClosure,
        request: ProcessingRequest,
    ) -> tuple[FailureDetail, ...]:
        selected = set(closure.node_ids)
        required_roles = {
            item.role
            for node in plan.nodes
            if node.id in selected
            for item in node.dataset_inputs
            if item.required
        }
        available_roles = {binding.role for binding in request.datasets.values}
        return tuple(
            FailureDetail(
                FailureCategory.REQUEST,
                "MISSING_DATASET_ROLE",
                f"Required dataset role {role.value} is not bound.",
            )
            for role in sorted(
                required_roles - available_roles,
                key=lambda value: value.value,
            )
        )

    @staticmethod
    def _context_requirement(
        plan: CompiledPlan,
        closure: TargetClosure,
    ) -> ContextRequirementSpec:
        selected = set(closure.node_ids)
        nodes = tuple(node for node in plan.nodes if node.id in selected)
        return ContextRequirementSpec(
            before_samples=max(
                (node.context.before_samples for node in nodes),
                default=0,
            ),
            after_samples=max(
                (node.context.after_samples for node in nodes),
                default=0,
            ),
        )

    @staticmethod
    def _validate_aligned_roles(
        aligned: AlignedDatasets,
        request: ProcessingRequest,
    ) -> None:
        expected = {binding.role for binding in request.datasets.values}
        actual = {dataset.role for dataset in aligned.values}
        if actual != expected:
            raise RuntimeError("The dataset aligner changed the requested role set.")

    @staticmethod
    def _predecessors(
        closure: TargetClosure,
    ) -> dict[CalculationNodeId, tuple[CalculationNodeId, ...]]:
        return {
            node_id: tuple(
                edge.producer
                for edge in closure.edges
                if edge.consumer == node_id
            )
            for node_id in closure.node_ids
        }

    @staticmethod
    def _validate_execution(
        node: CompiledNodeSpec,
        execution: PluginExecutionResult,
    ) -> tuple[NodeStatus, FailureDetail | None]:
        if execution.node_id != node.id:
            raise RuntimeError("The plugin result belongs to a different node.")
        returned_ids = tuple(
            artifact.artifact_id for artifact in execution.scalar_results
        ) + tuple(artifact.id for artifact in execution.table_artifacts)
        if set(returned_ids) != set(node.produces):
            raise RuntimeError("The plugin result does not match declared node outputs.")

        statuses = {artifact.status for artifact in execution.scalar_results}
        if NodeStatus.NOT_CALCULATED in statuses:
            raise RuntimeError("Only the scheduler may mark an output not calculated.")
        if len(statuses) > 1:
            raise RuntimeError("One node invocation returned mixed output statuses.")
        if statuses == {NodeStatus.FAILED}:
            if execution.table_artifacts:
                raise RuntimeError("A failed node cannot also return table artifacts.")
            failure = execution.scalar_results[0].failure
            if failure is None:
                raise RuntimeError("A failed node result requires failure detail.")
            return NodeStatus.FAILED, failure

        for artifact in execution.scalar_results:
            provenance = artifact.provenance
            if provenance is None or provenance.node_id != node.id:
                raise RuntimeError("A successful node result requires matching provenance.")
        return NodeStatus.SUCCEEDED, None

    @staticmethod
    def _instance_record(
        node: CompiledNodeSpec,
        scope: ResolvedScope,
        status: NodeStatus,
        failure: FailureDetail | None,
    ) -> ExecutionInstanceStatusRecord:
        return ExecutionInstanceStatusRecord(
            execution_instance=ExecutionInstanceId(
                f"instance.{node.id.value}.{scope.requested.id.value}"
            ),
            node_id=node.id,
            scope=scope.requested.id,
            occurrence=None,
            status=status,
            failure=failure,
        )

    @staticmethod
    def _result_records(
        plan: CompiledPlan,
        closure: TargetClosure,
        node: CompiledNodeSpec,
        scope: ResolvedScope,
        artifacts: tuple[ArtifactResult, ...],
    ) -> tuple[ResultRecord, ...]:
        selected_targets = tuple(
            target
            for target in plan.targets
            if target.id in closure.target_ids
        )
        return tuple(
            ResultRecord(
                node_id=node.id,
                execution_instance=ExecutionInstanceId(
                    f"instance.{node.id.value}.{scope.requested.id.value}"
                ),
                target_id=target.id,
                dataset_role=DatasetRole("primary"),
                scope=scope.requested.id,
                occurrence=None,
                scope_ancestry=scope.ancestry,
                artifact=artifact,
            )
            for artifact in artifacts
            for target in selected_targets
            if artifact.artifact_id in target.exports
        )

    @staticmethod
    def _report_status(
        instances: tuple[ExecutionInstanceStatusRecord, ...],
    ) -> ReportStatus:
        succeeded = sum(
            instance.status is NodeStatus.SUCCEEDED for instance in instances
        )
        if succeeded == len(instances):
            return ReportStatus.SUCCESS
        if succeeded:
            return ReportStatus.PARTIAL_SUCCESS
        return ReportStatus.FAILED
