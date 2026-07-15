"""Runtime-owned catalog snapshot consumed by the plugin declaration mapper."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.identifiers import ArtifactId, ChannelId, ParameterId
from ...domain.units import QuantityKind, Unit


@dataclass(frozen=True, slots=True)
class ChannelDefinition:
    id: ChannelId
    artifact: ArtifactId
    quantity_kind: QuantityKind


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    id: ParameterId
    artifact: ArtifactId
    quantity_kind: QuantityKind


@dataclass(frozen=True, slots=True)
class RuntimeCatalogSnapshot:
    """Validated runtime values; it contains no generated plugin references."""

    channels: tuple[ChannelDefinition, ...]
    parameters: tuple[ParameterDefinition, ...]
    units: tuple[Unit, ...]

    def __post_init__(self) -> None:
        _require_unique(self.channels, "id", "channel IDs")
        _require_unique(self.channels, "artifact", "channel artifacts")
        _require_unique(self.parameters, "id", "parameter IDs")
        _require_unique(self.parameters, "artifact", "parameter artifacts")
        _require_unique(self.units, "key", "unit keys")
        _require_unique(self.units, "symbol", "unit symbols")


def _require_unique(values: tuple[object, ...], field: str, label: str) -> None:
    members = tuple(getattr(value, field) for value in values)
    if len(members) != len(set(members)):
        raise ValueError(f"Runtime catalog {label} must be unique.")
