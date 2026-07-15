from __future__ import annotations

from dataclasses import replace

from pp_fx_architecture_examples.application.contracts.plans import (
    CompiledGraph,
    CompiledNodeKind,
    CompiledNodeSpec,
    ContentHash,
    FunctionPackLock,
    GraphCompilationResult,
    GraphNodeSpec,
    GraphValidationCode,
    ProcessingTarget,
)
from pp_fx_architecture_examples.application.services.graph_compiler import (
    compile_static_graph,
    select_target_closure,
)
from pp_fx_architecture_examples.domain.graph import (
    ArtifactInput,
    ArtifactKind,
    ArtifactOutput,
    ArtifactSource,
    ScopeEdgeMode,
)
from pp_fx_architecture_examples.domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    FunctionPackId,
    ProcessingTargetId,
)

PACK = FunctionPackLock(
    id=FunctionPackId("example.analysis"),
    version="1.0.0",
    distribution_hash=ContentHash("sha256", "a" * 64),
    declaration_hash=ContentHash("sha256", "b" * 64),
)
RAW = ArtifactId("raw.vehicle.brake_pressure")
ENERGY = ArtifactId("derived.brake.energy")
WINDOWS = ArtifactId("detected.brake.windows")
KPI = ArtifactId("result.brake.energy")
METRIC = ArtifactId("metric.brake.energy.mean")
AERO = ArtifactId("result.aero.balance")


def node(
    name: str,
    *,
    inputs: tuple[ArtifactInput, ...],
    outputs: tuple[ArtifactOutput, ...],
    kind: CompiledNodeKind,
) -> GraphNodeSpec:
    specification = CompiledNodeSpec(
        id=CalculationNodeId(name),
        pack=PACK,
        consumes=tuple(value.artifact for value in inputs),
        produces=tuple(value.artifact for value in outputs),
        kind=kind,
    )
    return GraphNodeSpec(specification, inputs, outputs)


def braking_fixture() -> tuple[
    tuple[ArtifactSource, ...],
    tuple[GraphNodeSpec, ...],
    tuple[ProcessingTarget, ...],
]:
    sources = (ArtifactSource(ArtifactOutput(RAW, ArtifactKind.RAW_CHANNEL)),)
    nodes = (
        node(
            "example.metric",
            inputs=(ArtifactInput(KPI, ArtifactKind.SCALAR_KPI, ScopeEdgeMode.FAN_IN_SELECTED_CHILDREN),),
            outputs=(ArtifactOutput(METRIC, ArtifactKind.METRIC),),
            kind=CompiledNodeKind.METRIC,
        ),
        node(
            "example.energy",
            inputs=(ArtifactInput(RAW, ArtifactKind.RAW_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
            outputs=(ArtifactOutput(ENERGY, ArtifactKind.DERIVED_CHANNEL),),
            kind=CompiledNodeKind.DERIVED_CHANNEL,
        ),
        node(
            "example.aero",
            inputs=(ArtifactInput(RAW, ArtifactKind.RAW_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
            outputs=(ArtifactOutput(AERO, ArtifactKind.SCALAR_KPI),),
            kind=CompiledNodeKind.KPI,
        ),
        node(
            "example.kpi",
            inputs=(
                ArtifactInput(ENERGY, ArtifactKind.DERIVED_CHANNEL, ScopeEdgeMode.SAME_SCOPE),
                ArtifactInput(
                    WINDOWS,
                    ArtifactKind.DETECTED_WINDOW_SET,
                    ScopeEdgeMode.EACH_SELECTED_CHILD_SCOPE,
                ),
            ),
            outputs=(ArtifactOutput(KPI, ArtifactKind.SCALAR_KPI),),
            kind=CompiledNodeKind.KPI,
        ),
        node(
            "example.detector",
            inputs=(ArtifactInput(RAW, ArtifactKind.RAW_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
            outputs=(ArtifactOutput(WINDOWS, ArtifactKind.DETECTED_WINDOW_SET),),
            kind=CompiledNodeKind.WINDOW_DETECTOR,
        ),
    )
    targets = (
        ProcessingTarget(ProcessingTargetId("target.braking"), (METRIC,)),
        ProcessingTarget(ProcessingTargetId("target.aero"), (AERO,)),
    )
    return sources, nodes, targets


def compiled_fixture() -> CompiledGraph:
    result = compile_static_graph(*braking_fixture())
    assert result.graph is not None
    return result.graph


def test_small_graph_has_deterministic_topological_order() -> None:
    graph = compiled_fixture()

    assert graph.topological_order == (
        CalculationNodeId("example.aero"),
        CalculationNodeId("example.detector"),
        CalculationNodeId("example.energy"),
        CalculationNodeId("example.kpi"),
        CalculationNodeId("example.metric"),
    )


def test_compiled_edges_retain_typed_artifacts_and_scope_semantics() -> None:
    graph = compiled_fixture()
    edges = {
        (edge.producer.value, edge.consumer.value): (edge.kind, edge.scope_mode)
        for edge in graph.edges
    }

    assert edges[("example.energy", "example.kpi")] == (
        ArtifactKind.DERIVED_CHANNEL,
        ScopeEdgeMode.SAME_SCOPE,
    )
    assert edges[("example.detector", "example.kpi")] == (
        ArtifactKind.DETECTED_WINDOW_SET,
        ScopeEdgeMode.EACH_SELECTED_CHILD_SCOPE,
    )
    assert edges[("example.kpi", "example.metric")] == (
        ArtifactKind.SCALAR_KPI,
        ScopeEdgeMode.FAN_IN_SELECTED_CHILDREN,
    )


def test_selected_target_closure_excludes_unselected_branch() -> None:
    graph = compiled_fixture()

    closure = select_target_closure(
        graph,
        (ProcessingTargetId("target.braking"),),
    )

    assert closure.node_ids == (
        CalculationNodeId("example.detector"),
        CalculationNodeId("example.energy"),
        CalculationNodeId("example.kpi"),
        CalculationNodeId("example.metric"),
    )
    assert CalculationNodeId("example.aero") not in closure.node_ids
    assert closure.exports == (METRIC,)


def test_missing_producer_is_rejected_with_static_validation() -> None:
    missing = ArtifactId("derived.missing")
    candidate = node(
        "example.consumer",
        inputs=(ArtifactInput(missing, ArtifactKind.DERIVED_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
        outputs=(ArtifactOutput(KPI, ArtifactKind.SCALAR_KPI),),
        kind=CompiledNodeKind.KPI,
    )

    result = compile_static_graph(
        (),
        (candidate,),
        (ProcessingTarget(ProcessingTargetId("target.kpi"), (KPI,)),),
    )

    assert_invalid(result, GraphValidationCode.MISSING_PRODUCER)


def test_duplicate_producer_is_rejected_with_static_validation() -> None:
    first = node(
        "example.first",
        inputs=(),
        outputs=(ArtifactOutput(KPI, ArtifactKind.SCALAR_KPI),),
        kind=CompiledNodeKind.KPI,
    )
    second = replace(
        first,
        specification=replace(first.specification, id=CalculationNodeId("example.second")),
    )

    result = compile_static_graph(
        (),
        (first, second),
        (ProcessingTarget(ProcessingTargetId("target.kpi"), (KPI,)),),
    )

    assert_invalid(result, GraphValidationCode.DUPLICATE_PRODUCER)


def test_cycle_is_rejected_with_static_validation() -> None:
    left_artifact = ArtifactId("derived.left")
    right_artifact = ArtifactId("derived.right")
    left = node(
        "example.left",
        inputs=(ArtifactInput(right_artifact, ArtifactKind.DERIVED_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
        outputs=(ArtifactOutput(left_artifact, ArtifactKind.DERIVED_CHANNEL),),
        kind=CompiledNodeKind.DERIVED_CHANNEL,
    )
    right = node(
        "example.right",
        inputs=(ArtifactInput(left_artifact, ArtifactKind.DERIVED_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
        outputs=(ArtifactOutput(right_artifact, ArtifactKind.DERIVED_CHANNEL),),
        kind=CompiledNodeKind.DERIVED_CHANNEL,
    )

    result = compile_static_graph(
        (),
        (left, right),
        (ProcessingTarget(ProcessingTargetId("target.left"), (left_artifact,)),),
    )

    assert_invalid(result, GraphValidationCode.CYCLE)


def test_graph_compilation_rejects_input_output_contract_mismatch() -> None:
    candidate = node(
        "example.consumer",
        inputs=(),
        outputs=(ArtifactOutput(KPI, ArtifactKind.SCALAR_KPI),),
        kind=CompiledNodeKind.KPI,
    )
    invalid = replace(
        candidate,
        inputs=(ArtifactInput(RAW, ArtifactKind.RAW_CHANNEL, ScopeEdgeMode.SAME_SCOPE),),
    )

    result = compile_static_graph(
        (ArtifactSource(ArtifactOutput(RAW, ArtifactKind.RAW_CHANNEL)),),
        (invalid,),
        (ProcessingTarget(ProcessingTargetId("target.kpi"), (KPI,)),),
    )

    assert_invalid(result, GraphValidationCode.NODE_CONTRACT_MISMATCH)


def assert_invalid(
    result: GraphCompilationResult,
    expected_code: GraphValidationCode,
) -> None:
    assert result.graph is None
    assert result.validation.is_valid is False
    assert expected_code in tuple(failure.code for failure in result.validation.failures)
