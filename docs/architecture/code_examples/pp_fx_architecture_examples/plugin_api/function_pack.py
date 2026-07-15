from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .decorators import node_declaration

PluginNode = Callable[..., object]


@dataclass(frozen=True, slots=True)
class CatalogRequirement:
    id: str
    version_range: str

    def __post_init__(self) -> None:
        if not self.id or not self.version_range:
            raise ValueError("Catalog ID and version range are required.")


@dataclass(frozen=True, slots=True)
class FunctionPackDefinition:
    """Explicit immutable export manifest; it performs no discovery."""

    id: str
    version: str
    plugin_api_version: str
    catalog_requirements: tuple[CatalogRequirement, ...]
    nodes: tuple[PluginNode, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.version or not self.plugin_api_version:
            raise ValueError("Pack ID, version, and plugin API version are required.")

        node_ids = tuple(node_declaration(node).id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("A function pack cannot export duplicate node IDs.")
