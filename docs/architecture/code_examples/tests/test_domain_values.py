from __future__ import annotations

import ast
import sys
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from pp_fx_architecture_examples.domain.failures import (
    FailureCategory,
    FailureDetail,
)
from pp_fx_architecture_examples.domain.graph import (
    ArtifactDependency,
    ArtifactKind,
    ScopeEdgeMode,
)
from pp_fx_architecture_examples.domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    ChannelId,
    ParameterId,
    ScopeId,
)
from pp_fx_architecture_examples.domain.results import (
    ArtifactResult,
    NodeStatus,
    ResultProvenance,
)
from pp_fx_architecture_examples.domain.scopes import (
    BoundaryMode,
    CoordinateAxis,
    RequestedScope,
    ResolvedScope,
)
from pp_fx_architecture_examples.domain.units import Quantity, QuantityKind, Unit

DOMAIN_ROOT = Path(__file__).resolve().parents[1] / "pp_fx_architecture_examples/domain"
DISTANCE = QuantityKind("distance")
METRE = Unit(key="si.metre", symbol="m", quantity_kind=DISTANCE)
AXIS = CoordinateAxis(
    id=ChannelId("lap.distance"),
    quantity_kind=DISTANCE,
    canonical_unit=METRE,
)


@pytest.mark.parametrize(
    "identifier_type",
    [ChannelId, ParameterId, ScopeId, ArtifactId, CalculationNodeId],
)
def test_canonical_ids_accept_qualified_lowercase_values(identifier_type: type) -> None:
    identifier = identifier_type("vehicle.brake_pressure.front_left")

    assert str(identifier) == "vehicle.brake_pressure.front_left"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "vehicle",
        "Vehicle.speed",
        ".vehicle.speed",
        "vehicle..speed",
        "vehicle-speed",
        "vehicle.2speed",
        "vehicle.speed ",
    ],
)
def test_canonical_ids_reject_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        ChannelId(value)


def test_domain_values_are_immutable() -> None:
    channel = ChannelId("vehicle.speed")
    quantity = Quantity(Decimal("500"), METRE)

    with pytest.raises(FrozenInstanceError):
        channel.value = "vehicle.velocity"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        quantity.magnitude = Decimal("700")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        METRE.symbol = "metre"  # type: ignore[misc]


def test_child_scope_retains_ancestry_and_stays_inside_parent() -> None:
    parent = resolved_scope("scope.sector", "0", "1000")
    child = resolved_scope("scope.braking", "100", "250", parent=parent)

    assert child.ancestry == (ScopeId("scope.sector"), ScopeId("scope.braking"))

    with pytest.raises(ValueError, match="inside its parent"):
        resolved_scope("scope.outside", "-1", "250", parent=parent)


def test_scope_bounds_require_one_axis_unit_and_increasing_values() -> None:
    second = Unit(
        key="si.second",
        symbol="s",
        quantity_kind=QuantityKind("time"),
    )

    with pytest.raises(ValueError, match="same unit"):
        RequestedScope(
            id=ScopeId("scope.invalid_units"),
            axis=AXIS,
            start=Quantity(Decimal("1"), METRE),
            end=Quantity(Decimal("2"), second),
        )

    with pytest.raises(ValueError, match="axis quantity"):
        RequestedScope(
            id=ScopeId("scope.invalid_quantity"),
            axis=AXIS,
            start=Quantity(Decimal("1"), second),
            end=Quantity(Decimal("2"), second),
        )

    with pytest.raises(ValueError, match="start before end"):
        requested_scope("scope.reversed", "10", "5")


def test_unit_bearing_results_cannot_be_unlabelled_numbers() -> None:
    provenance = ResultProvenance(
        node_id=CalculationNodeId("standard.speed.maximum"),
        input_artifacts=(ArtifactId("raw.vehicle.speed"),),
        calculation_unit=METRE,
    )

    result = ArtifactResult(
        artifact_id=ArtifactId("result.speed.maximum"),
        status=NodeStatus.SUCCEEDED,
        value=Quantity(Decimal("42"), METRE),
        provenance=provenance,
    )

    assert isinstance(result.value, Quantity)
    assert result.value.unit == METRE

    with pytest.raises(ValueError, match="typed Quantity"):
        ArtifactResult(
            artifact_id=ArtifactId("result.speed.unlabelled"),
            status=NodeStatus.SUCCEEDED,
            value=Decimal("42"),  # type: ignore[arg-type]
            provenance=provenance,
        )


def test_result_status_and_failure_must_agree() -> None:
    failure = FailureDetail(
        category=FailureCategory.NODE,
        code="MISSING_CHANNEL",
        message="Required speed channel is unavailable.",
    )

    failed = ArtifactResult(
        artifact_id=ArtifactId("result.speed.maximum"),
        status=NodeStatus.FAILED,
        failure=failure,
    )
    assert failed.failure == failure

    with pytest.raises(ValueError, match="requires a failure"):
        ArtifactResult(
            artifact_id=ArtifactId("result.speed.invalid"),
            status=NodeStatus.FAILED,
        )

    with pytest.raises(ValueError, match="node-level failure"):
        ArtifactResult(
            artifact_id=ArtifactId("result.speed.wrong_category"),
            status=NodeStatus.FAILED,
            failure=FailureDetail(
                category=FailureCategory.REQUEST,
                code="INVALID_REQUEST",
                message="Request failures do not belong in artifact results.",
            ),
        )


def test_dependency_edges_reject_direct_self_cycles() -> None:
    node = CalculationNodeId("standard.speed.maximum")

    with pytest.raises(ValueError, match="itself"):
        ArtifactDependency(
            producer=node,
            consumer=node,
            artifact=ArtifactId("derived.vehicle.speed"),
            kind=ArtifactKind.DERIVED_CHANNEL,
            scope_mode=ScopeEdgeMode.SAME_SCOPE,
        )


def test_domain_modules_use_only_the_standard_library_and_domain_relatives() -> None:
    forbidden_imports: list[str] = []

    for module_path in sorted(DOMAIN_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 1:
                    continue
                if node.level > 1:
                    location = f"{module_path.name}:{node.lineno}:outside-domain-relative"
                    forbidden_imports.append(location)
                    continue
                if node.module is None:
                    continue
                imported_names = (node.module,)
            else:
                continue

            for imported_name in imported_names:
                root_name = imported_name.partition(".")[0]
                if root_name not in sys.stdlib_module_names:
                    location = f"{module_path.name}:{node.lineno}:{imported_name}"
                    forbidden_imports.append(location)

    assert forbidden_imports == []


def requested_scope(scope_id: str, start: str, end: str) -> RequestedScope:
    return RequestedScope(
        id=ScopeId(scope_id),
        axis=AXIS,
        start=Quantity(Decimal(start), METRE),
        end=Quantity(Decimal(end), METRE),
    )


def resolved_scope(
    scope_id: str,
    start: str,
    end: str,
    *,
    parent: ResolvedScope | None = None,
) -> ResolvedScope:
    requested = requested_scope(scope_id, start, end)
    return ResolvedScope(
        requested=requested,
        effective_start=requested.start,
        effective_end=requested.end,
        boundary_mode=BoundaryMode.EXACT,
        parent=parent,
    )
