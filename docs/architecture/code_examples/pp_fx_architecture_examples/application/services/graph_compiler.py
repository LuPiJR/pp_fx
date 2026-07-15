"""Small deterministic static-graph compiler; not an execution scheduler."""

from __future__ import annotations

import heapq
from collections import Counter
from typing import TypeAlias

from ...domain.graph import (
    ArtifactDependency,
    ArtifactKind,
    ArtifactSource,
    ScopeEdgeMode,
)
from ...domain.identifiers import ArtifactId, CalculationNodeId, ProcessingTargetId
from ..contracts.plans import (
    CompiledGraph,
    GraphCompilationResult,
    GraphNodeSpec,
    GraphValidationCode,
    GraphValidationFailure,
    ProcessingTarget,
    StaticGraphValidationResult,
    TargetClosure,
)

ProducerIndex: TypeAlias = dict[
    ArtifactId,
    list[tuple[CalculationNodeId | None, ArtifactKind]],
]


def compile_static_graph(
    sources: tuple[ArtifactSource, ...],
    nodes: tuple[GraphNodeSpec, ...],
    targets: tuple[ProcessingTarget, ...],
) -> GraphCompilationResult:
    """Validate typed declarations and create an immutable static graph."""

    node_ids = tuple(node.specification.id for node in nodes)
    producers = _index_producers(sources, nodes)
    edges, dependency_failures = _build_dependencies(nodes, producers)
    topological_order = _topological_order(node_ids, edges)
    failures = (
        *_identity_failures(sources, nodes, targets),
        *_node_contract_failures(nodes),
        *_producer_failures(producers),
        *dependency_failures,
        *_target_failures(targets, nodes, producers),
        *_cycle_failures(node_ids, topological_order),
    )
    validation = StaticGraphValidationResult(_sorted_failures(list(failures)))
    if not validation.is_valid:
        return GraphCompilationResult(graph=None, validation=validation)

    graph = CompiledGraph(
        sources=tuple(sorted(sources, key=lambda source: source.output.artifact.value)),
        nodes=tuple(sorted(nodes, key=lambda node: node.specification.id.value)),
        edges=tuple(
            sorted(
                edges,
                key=lambda edge: (
                    edge.consumer.value,
                    edge.producer.value,
                    edge.artifact.value,
                ),
            )
        ),
        targets=tuple(sorted(targets, key=lambda target: target.id.value)),
        topological_order=topological_order,
    )
    return GraphCompilationResult(graph=graph, validation=validation)


def _identity_failures(
    sources: tuple[ArtifactSource, ...],
    nodes: tuple[GraphNodeSpec, ...],
    targets: tuple[ProcessingTarget, ...],
) -> tuple[GraphValidationFailure, ...]:
    return (
        *_duplicate_failures(
            tuple(node.specification.id for node in nodes),
            GraphValidationCode.DUPLICATE_NODE,
        ),
        *_duplicate_failures(
            tuple(source.output.artifact for source in sources),
            GraphValidationCode.DUPLICATE_SOURCE,
        ),
        *_duplicate_failures(
            tuple(target.id for target in targets),
            GraphValidationCode.DUPLICATE_TARGET,
        ),
    )


def _node_contract_failures(
    nodes: tuple[GraphNodeSpec, ...],
) -> tuple[GraphValidationFailure, ...]:
    failures: list[GraphValidationFailure] = []
    for node in nodes:
        consumed = tuple(value.artifact for value in node.inputs)
        produced = tuple(value.artifact for value in node.outputs)
        if consumed != node.specification.consumes:
            failures.append(
                _failure(
                    GraphValidationCode.NODE_CONTRACT_MISMATCH,
                    node.specification.id.value,
                    "Typed inputs must exactly match the mapped consumed artifacts.",
                )
            )
        if produced != node.specification.produces:
            failures.append(
                _failure(
                    GraphValidationCode.NODE_CONTRACT_MISMATCH,
                    node.specification.id.value,
                    "Typed outputs must exactly match the mapped produced artifacts.",
                )
            )
    return tuple(failures)


def _index_producers(
    sources: tuple[ArtifactSource, ...],
    nodes: tuple[GraphNodeSpec, ...],
) -> ProducerIndex:
    producers: ProducerIndex = {}
    for source in sources:
        producers.setdefault(source.output.artifact, []).append((None, source.output.kind))
    for node in nodes:
        for output in node.outputs:
            producers.setdefault(output.artifact, []).append(
                (node.specification.id, output.kind)
            )
    return producers


def _producer_failures(
    producers: ProducerIndex,
) -> tuple[GraphValidationFailure, ...]:
    return tuple(
        _failure(
            GraphValidationCode.DUPLICATE_PRODUCER,
            artifact.value,
            "An artifact must have exactly one source or calculation producer.",
        )
        for artifact, entries in producers.items()
        if len(entries) > 1
    )


def _build_dependencies(
    nodes: tuple[GraphNodeSpec, ...],
    producers: ProducerIndex,
) -> tuple[tuple[ArtifactDependency, ...], tuple[GraphValidationFailure, ...]]:
    edges: list[ArtifactDependency] = []
    failures: list[GraphValidationFailure] = []
    for node in nodes:
        for input_contract in node.inputs:
            producer_entries = producers.get(input_contract.artifact, [])
            if not producer_entries:
                failures.append(
                    _failure(
                        GraphValidationCode.MISSING_PRODUCER,
                        input_contract.artifact.value,
                        f"Node {node.specification.id.value!r} consumes an unknown artifact.",
                    )
                )
                continue
            if len(producer_entries) > 1:
                continue
            producer, output_kind = producer_entries[0]
            if output_kind != input_contract.kind:
                failures.append(
                    _failure(
                        GraphValidationCode.ARTIFACT_TYPE_MISMATCH,
                        input_contract.artifact.value,
                        "The consumer artifact kind disagrees with its producer.",
                    )
                )
            if producer is None:
                if input_contract.scope_mode is not ScopeEdgeMode.SAME_SCOPE:
                    failures.append(
                        _failure(
                            GraphValidationCode.INVALID_SOURCE_SCOPE,
                            input_contract.artifact.value,
                            "External sources can only enter a node at the same scope.",
                        )
                    )
                continue
            edges.append(
                ArtifactDependency(
                    producer=producer,
                    consumer=node.specification.id,
                    artifact=input_contract.artifact,
                    kind=input_contract.kind,
                    scope_mode=input_contract.scope_mode,
                )
            )
    return tuple(edges), tuple(failures)


def _target_failures(
    targets: tuple[ProcessingTarget, ...],
    nodes: tuple[GraphNodeSpec, ...],
    producers: ProducerIndex,
) -> tuple[GraphValidationFailure, ...]:
    node_producers = {
        output.artifact
        for node in nodes
        for output in node.outputs
        if len(producers[output.artifact]) == 1
    }
    return tuple(
        _failure(
            GraphValidationCode.MISSING_TARGET_EXPORT,
            f"{target.id.value}:{artifact.value}",
            "A public target export requires one calculation-node producer.",
        )
        for target in targets
        for artifact in target.exports
        if artifact not in node_producers
    )


def _cycle_failures(
    node_ids: tuple[CalculationNodeId, ...],
    topological_order: tuple[CalculationNodeId, ...],
) -> tuple[GraphValidationFailure, ...]:
    if len(topological_order) == len(set(node_ids)):
        return ()
    cyclic = sorted(set(node_ids) - set(topological_order), key=lambda value: value.value)
    return (
        _failure(
            GraphValidationCode.CYCLE,
            ",".join(node_id.value for node_id in cyclic),
            "The static calculation graph must be acyclic.",
        ),
    )


def select_target_closure(
    graph: CompiledGraph,
    target_ids: tuple[ProcessingTargetId, ...],
) -> TargetClosure:
    """Select only target producers and their transitive node dependencies."""

    if not target_ids or len(target_ids) != len(set(target_ids)):
        raise ValueError("Target selection requires unique named targets.")
    targets_by_id = {target.id: target for target in graph.targets}
    unknown = tuple(target_id for target_id in target_ids if target_id not in targets_by_id)
    if unknown:
        raise ValueError(f"Unknown processing target: {unknown[0].value}")

    exports = tuple(
        dict.fromkeys(
            artifact
            for target_id in target_ids
            for artifact in targets_by_id[target_id].exports
        )
    )
    producer_by_artifact = {
        output.artifact: node.specification.id
        for node in graph.nodes
        for output in node.outputs
    }
    predecessors: dict[CalculationNodeId, set[CalculationNodeId]] = {
        node.specification.id: set() for node in graph.nodes
    }
    for edge in graph.edges:
        predecessors[edge.consumer].add(edge.producer)

    selected: set[CalculationNodeId] = set()
    pending = [producer_by_artifact[artifact] for artifact in exports]
    while pending:
        node_id = pending.pop()
        if node_id in selected:
            continue
        selected.add(node_id)
        pending.extend(predecessors[node_id])

    ordered_nodes = tuple(
        node_id for node_id in graph.topological_order if node_id in selected
    )
    selected_edges = tuple(
        edge
        for edge in graph.edges
        if edge.producer in selected and edge.consumer in selected
    )
    return TargetClosure(target_ids, exports, ordered_nodes, selected_edges)


def _topological_order(
    node_ids: tuple[CalculationNodeId, ...],
    edges: tuple[ArtifactDependency, ...],
) -> tuple[CalculationNodeId, ...]:
    unique_nodes = set(node_ids)
    indegree = {node_id: 0 for node_id in unique_nodes}
    successors = {node_id: set() for node_id in unique_nodes}
    for edge in edges:
        if edge.consumer not in successors[edge.producer]:
            successors[edge.producer].add(edge.consumer)
            indegree[edge.consumer] += 1

    ready = [(node_id.value, node_id) for node_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    ordered: list[CalculationNodeId] = []
    while ready:
        _, node_id = heapq.heappop(ready)
        ordered.append(node_id)
        for successor in sorted(successors[node_id], key=lambda value: value.value):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, (successor.value, successor))
    return tuple(ordered)


def _duplicate_failures(
    values: tuple[object, ...],
    code: GraphValidationCode,
) -> tuple[GraphValidationFailure, ...]:
    counts = Counter(values)
    return tuple(
        _failure(code, str(value), "Static graph identities must be unique.")
        for value, count in counts.items()
        if count > 1
    )


def _failure(
    code: GraphValidationCode,
    reference: str,
    message: str,
) -> GraphValidationFailure:
    return GraphValidationFailure(code, reference, message)


def _sorted_failures(
    failures: list[GraphValidationFailure],
) -> tuple[GraphValidationFailure, ...]:
    return tuple(
        sorted(failures, key=lambda failure: (failure.code.value, failure.reference))
    )
