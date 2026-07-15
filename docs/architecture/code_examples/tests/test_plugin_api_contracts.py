from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path

import pytest

from pp_fx_architecture_examples.catalog.channels import brake, vehicle
from pp_fx_architecture_examples.domain.identifiers import ChannelId, ParameterId
from pp_fx_architecture_examples.domain.units import QuantityKind, Unit
from pp_fx_architecture_examples.function_pack.configuration import (
    BrakeWindowConfiguration,
)
from pp_fx_architecture_examples.function_pack.derived_channels import brake_power
from pp_fx_architecture_examples.function_pack.kpis import (
    maximum_brake_pressure,
    unexported_diagnostic,
)
from pp_fx_architecture_examples.function_pack.metrics import mean_maximum_brake_pressure
from pp_fx_architecture_examples.function_pack.pack import FUNCTION_PACK
from pp_fx_architecture_examples.function_pack.window_detectors import brake_windows
from pp_fx_architecture_examples.plugin_api.contracts import (
    ChannelRequirement,
    KpiInput,
    ScalarResultDefinition,
)
from pp_fx_architecture_examples.plugin_api.decorators import kpi, node_declaration
from pp_fx_architecture_examples.plugin_api.references import (
    ChannelRef,
    ParameterRef,
    QuantityRef,
    UnitRef,
)

EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "pp_fx_architecture_examples"


def test_decoration_attaches_immutable_metadata_without_registration() -> None:
    requirement = ChannelRequirement(channel=vehicle.speed)
    output = ScalarResultDefinition(
        artifact="example.speed.maximum",
        quantity=QuantityRef("speed"),
        unit=UnitRef("m/s", quantity=QuantityRef("speed")),
    )

    def calculate(data: KpiInput[None, object]) -> float:
        return 0.0

    undecorated_signature = inspect.signature(calculate)
    decorated = kpi(
        id="example.speed.maximum",
        requires_channels=(requirement,),
        output=output,
    )(calculate)

    declaration = node_declaration(decorated)
    assert decorated is calculate
    assert inspect.signature(decorated) == undecorated_signature
    assert declaration.requires_channels == (requirement,)
    assert decorated not in FUNCTION_PACK.nodes

    with pytest.raises(FrozenInstanceError):
        declaration.id = "changed"  # type: ignore[misc]


def test_decorator_rejects_mutable_node_configuration() -> None:
    @dataclass
    class MutableConfiguration:
        threshold: float

    def calculate(data: KpiInput[MutableConfiguration, object]) -> float:
        return 0.0

    with pytest.raises(TypeError, match="frozen dataclass"):
        kpi(
            id="example.mutable_configuration",
            configuration=MutableConfiguration,
            output=ScalarResultDefinition(
                artifact="example.mutable_configuration",
                quantity=QuantityRef("ratio"),
                unit=UnitRef("percent", quantity=QuantityRef("ratio")),
            ),
        )(calculate)


def test_pack_manifest_exports_decorated_nodes_explicitly() -> None:
    assert FUNCTION_PACK.nodes == (
        brake_power,
        brake_windows,
        maximum_brake_pressure,
        mean_maximum_brake_pressure,
    )
    assert unexported_diagnostic not in FUNCTION_PACK.nodes

    with pytest.raises(FrozenInstanceError):
        FUNCTION_PACK.version = "changed"  # type: ignore[misc]


def test_node_signatures_requirements_and_configuration_are_inspectable() -> None:
    expected_kinds = {
        brake_power: "derived_channel",
        brake_windows: "window_detector",
        maximum_brake_pressure: "kpi",
        mean_maximum_brake_pressure: "metric",
    }

    for node, expected_kind in expected_kinds.items():
        signature = inspect.signature(node)
        assert tuple(signature.parameters) == ("data",)
        assert signature.return_annotation is not inspect.Signature.empty
        assert node_declaration(node).kind.value == expected_kind

    detector = node_declaration(brake_windows)
    assert detector.configuration is BrakeWindowConfiguration
    assert detector.requires_channels[0].channel is brake.pressure_front_left
    assert detector.requires_channels[0].unit.value == "bar"
    assert detector.context.before_samples == 1
    assert detector.context.after_samples == 1

    derived_declaration = node_declaration(brake_power)
    assert (
        derived_declaration.requires_parameters[0].parameter.value
        == "vehicle.geometry.wheel_radius.front_left"
    )
    metric_declaration = node_declaration(mean_maximum_brake_pressure)
    assert metric_declaration.requires_results[0].artifact == (
        "example.braking.maximum_pressure"
    )


def test_generated_catalog_namespace_exposes_plugin_owned_references() -> None:
    assert isinstance(vehicle.speed, ChannelRef)
    assert isinstance(brake.pressure_front_left, ChannelRef)
    assert brake.pressure_front_left.value == "vehicle.brake_pressure.front_left"


def test_plugin_references_are_nominally_distinct_from_runtime_ids() -> None:
    plugin_reference = ChannelRef("vehicle.speed")
    runtime_id = ChannelId("vehicle.speed")

    assert plugin_reference.value == runtime_id.value
    assert plugin_reference != runtime_id
    assert type(plugin_reference) is not type(runtime_id)
    type_pairs = (
        (ChannelRef, ChannelId),
        (ParameterRef, ParameterId),
        (QuantityRef, QuantityKind),
        (UnitRef, Unit),
    )
    assert all(plugin_type is not runtime_type for plugin_type, runtime_type in type_pairs)


def test_plugin_packages_do_not_import_runtime_layers() -> None:
    forbidden_roots = {
        "pp_fx_architecture_examples.domain",
        "pp_fx_architecture_examples.application",
        "pp_fx_architecture_examples.adapters",
        "pp_fx_architecture_examples.delivery",
        "pp_fx_architecture_examples.composition",
        "pp_fx_runtime",
    }
    violations: list[str] = []

    forbidden_relative_roots = {
        "domain",
        "application",
        "adapters",
        "delivery",
        "composition",
    }

    for package_name in ("plugin_api", "catalog", "function_pack"):
        for source_file in sorted((EXAMPLE_ROOT / package_name).rglob("*.py")):
            tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
            for node in ast.walk(tree):
                imported: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    imported = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = (node.module,)

                for name in imported:
                    forbidden_absolute = any(
                        name == root or name.startswith(f"{root}.")
                        for root in forbidden_roots
                    )
                    forbidden_relative = (
                        isinstance(node, ast.ImportFrom)
                        and node.level > 0
                        and name.partition(".")[0] in forbidden_relative_roots
                    )
                    if forbidden_absolute or forbidden_relative:
                        violations.append(f"{source_file.name}:{node.lineno}:{name}")

    assert violations == []
