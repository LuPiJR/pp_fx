from __future__ import annotations

import ast
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from pp_fx_architecture_examples.adapters.plugin_mapping.catalog import (
    ChannelDefinition,
    ParameterDefinition,
    RuntimeCatalogSnapshot,
)
from pp_fx_architecture_examples.adapters.plugin_mapping.mapper import (
    PluginDeclarationMapper,
    ReferenceMappingError,
)
from pp_fx_architecture_examples.adapters.plugin_mapping.registry import (
    CallableBindingKey,
    CallableBindingNotFound,
    CallableRegistry,
    InMemoryCallableRegistry,
)
from pp_fx_architecture_examples.adapters.plugin_mapping.validation import (
    MappingFailureCode,
)
from pp_fx_architecture_examples.application.contracts.plans import (
    ContentHash,
    FunctionPackLock,
)
from pp_fx_architecture_examples.catalog.channels import vehicle
from pp_fx_architecture_examples.catalog.parameters import geometry
from pp_fx_architecture_examples.domain.identifiers import (
    ArtifactId,
    ChannelId,
    FunctionPackId,
    ParameterId,
)
from pp_fx_architecture_examples.domain.units import QuantityKind, Unit
from pp_fx_architecture_examples.function_pack.kpis import maximum_brake_pressure
from pp_fx_architecture_examples.plugin_api.contracts import ChannelRequirement
from pp_fx_architecture_examples.plugin_api.decorators import node_declaration
from pp_fx_architecture_examples.plugin_api.references import ChannelRef
from pp_fx_architecture_examples.plugin_api.units import units

MAPPING_ROOT = (
    Path(__file__).resolve().parents[1]
    / "pp_fx_architecture_examples/adapters/plugin_mapping"
)
SPEED = QuantityKind("speed")
PRESSURE = QuantityKind("pressure")
LENGTH = QuantityKind("length")
METRE_PER_SECOND = Unit("si.metre_per_second", "m/s", SPEED)
BAR = Unit("metric.bar", "bar", PRESSURE)
METRE = Unit("si.metre", "m", LENGTH)
DISTRIBUTION_HASH = ContentHash("sha256", "a" * 64)
DECLARATION_HASH = ContentHash("sha256", "b" * 64)
PACK_LOCK = FunctionPackLock(
    id=FunctionPackId("example.braking"),
    version="1.0.0",
    distribution_hash=DISTRIBUTION_HASH,
    declaration_hash=DECLARATION_HASH,
)
CATALOG = RuntimeCatalogSnapshot(
    channels=(
        ChannelDefinition(
            id=ChannelId("vehicle.speed"),
            artifact=ArtifactId("raw.vehicle.speed"),
            quantity_kind=SPEED,
        ),
        ChannelDefinition(
            id=ChannelId("vehicle.brake_pressure.front_left"),
            artifact=ArtifactId("raw.vehicle.brake_pressure.front_left"),
            quantity_kind=PRESSURE,
        ),
    ),
    parameters=(
        ParameterDefinition(
            id=ParameterId("vehicle.geometry.wheel_radius.front_left"),
            artifact=ArtifactId("parameter.vehicle.geometry.wheel_radius.front_left"),
            quantity_kind=LENGTH,
        ),
    ),
    units=(METRE_PER_SECOND, BAR, METRE),
)


def test_known_plugin_references_map_by_canonical_value() -> None:
    mapper = PluginDeclarationMapper(CATALOG)

    assert mapper.map_channel(vehicle.speed) == ChannelId("vehicle.speed")
    assert mapper.map_parameter(geometry.wheel_radius_front_left) == ParameterId(
        "vehicle.geometry.wheel_radius.front_left"
    )


def test_unknown_reference_fails_with_typed_mapping_detail() -> None:
    mapper = PluginDeclarationMapper(CATALOG)

    with pytest.raises(ReferenceMappingError) as captured:
        mapper.map_channel(ChannelRef("customer.unknown_channel"))

    assert captured.value.failure.code is MappingFailureCode.UNKNOWN_CHANNEL
    assert captured.value.failure.reference == "customer.unknown_channel"


def test_dimensionally_incompatible_requirement_fails_static_validation() -> None:
    mapper = PluginDeclarationMapper(CATALOG)
    declaration = replace(
        node_declaration(maximum_brake_pressure),
        requires_channels=(ChannelRequirement(vehicle.speed, unit=units.bar),),
    )

    result = mapper.map_declaration(declaration, pack=PACK_LOCK)

    assert result.specification is None
    assert result.validation.is_valid is False
    assert tuple(failure.code for failure in result.validation.failures) == (
        MappingFailureCode.INCOMPATIBLE_DIMENSION,
    )


def test_declaration_maps_to_plugin_free_serializable_compiled_spec() -> None:
    mapper = PluginDeclarationMapper(CATALOG)

    result = mapper.map_declaration(
        node_declaration(maximum_brake_pressure),
        pack=PACK_LOCK,
    )

    assert result.validation.is_valid is True
    assert result.specification is not None
    assert result.specification.id.value == "example.braking.maximum_pressure"
    assert result.specification.consumes == (
        ArtifactId("raw.vehicle.brake_pressure.front_left"),
    )
    assert result.specification.produces == (
        ArtifactId("example.braking.maximum_pressure"),
    )
    assert result.specification.kind.value == "kpi"
    assert result.specification.channel_inputs[0].channel == ChannelId(
        "vehicle.brake_pressure.front_left"
    )
    assert result.specification.channel_inputs[0].calculation_unit == BAR
    assert result.specification.output is not None
    assert result.specification.output.quantity_kind == PRESSURE
    assert result.specification.output.calculation_unit == BAR
    assert json.loads(json.dumps(asdict(result.specification)))["id"]["value"] == (
        "example.braking.maximum_pressure"
    )
    assert not contains_plugin_value_or_callable(result.specification)


def test_callable_resolution_requires_the_exact_locked_key() -> None:
    mapper = PluginDeclarationMapper(CATALOG)
    mapped = mapper.map_declaration(
        node_declaration(maximum_brake_pressure),
        pack=PACK_LOCK,
    )
    assert mapped.specification is not None
    key = CallableBindingKey.from_specification(mapped.specification)
    registry: CallableRegistry = InMemoryCallableRegistry()
    registry.bind(key, maximum_brake_pressure)

    assert registry.resolve(key) is maximum_brake_pressure

    mismatched_keys = (
        replace(key, artifact_hash=ContentHash("sha256", "c" * 64)),
        replace(key, declaration_hash=ContentHash("sha256", "d" * 64)),
    )
    for mismatched_key in mismatched_keys:
        with pytest.raises(CallableBindingNotFound):
            registry.resolve(mismatched_key)


def test_mapping_adapter_imports_only_plugin_api_and_inward_runtime_values() -> None:
    violations: list[str] = []

    for source_file in sorted(MAPPING_ROOT.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), source_file.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names = tuple(alias.name for alias in node.names)
                for imported_name in imported_names:
                    if imported_name.partition(".")[0] not in sys.stdlib_module_names:
                        violations.append(
                            f"{source_file.name}:{node.lineno}:{imported_name}"
                        )
                continue

            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.level == 1:
                continue
            if node.level == 3 and node.module.startswith(
                ("domain.", "application.contracts.", "plugin_api.")
            ):
                continue
            if node.level == 0 and (
                node.module == "__future__"
                or node.module.partition(".")[0] in sys.stdlib_module_names
            ):
                continue
            violations.append(f"{source_file.name}:{node.lineno}:{node.module}")

    assert violations == []


def contains_plugin_value_or_callable(value: object) -> bool:
    if callable(value):
        return True
    if type(value).__module__.startswith("pp_fx_architecture_examples.plugin_api"):
        return True
    if hasattr(value, "__dataclass_fields__"):
        return any(
            contains_plugin_value_or_callable(getattr(value, field_name))
            for field_name in value.__dataclass_fields__  # type: ignore[attr-defined]
        )
    if isinstance(value, tuple):
        return any(contains_plugin_value_or_callable(item) for item in value)
    return False
