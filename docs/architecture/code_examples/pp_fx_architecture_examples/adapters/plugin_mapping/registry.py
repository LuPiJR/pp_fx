"""Adapter-owned callable binding identity and exact-match registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ...application.contracts.plans import CompiledNodeSpec, ContentHash
from ...domain.identifiers import CalculationNodeId, FunctionPackId

PluginCallable = Callable[..., object]


@dataclass(frozen=True, slots=True)
class CallableBindingKey:
    pack_id: FunctionPackId
    version: str
    artifact_hash: ContentHash
    declaration_hash: ContentHash
    node_id: CalculationNodeId

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("A callable binding key requires an exact pack version.")

    @classmethod
    def from_specification(cls, node: CompiledNodeSpec) -> CallableBindingKey:
        return cls(
            pack_id=node.pack.id,
            version=node.pack.version,
            artifact_hash=node.pack.distribution_hash,
            declaration_hash=node.pack.declaration_hash,
            node_id=node.id,
        )


class CallableBindingNotFound(LookupError):
    def __init__(self, key: CallableBindingKey) -> None:
        self.key = key
        super().__init__(f"No callable is bound for locked key {key!r}.")


class CallableRegistry(Protocol):
    def bind(self, key: CallableBindingKey, function: PluginCallable) -> None: ...

    def resolve(self, key: CallableBindingKey) -> PluginCallable: ...


class InMemoryCallableRegistry:
    """Small explanatory registry; it discovers and executes nothing."""

    def __init__(self) -> None:
        self._bindings: dict[CallableBindingKey, PluginCallable] = {}

    def bind(self, key: CallableBindingKey, function: PluginCallable) -> None:
        if not callable(function):
            raise TypeError("A callable registry can bind only callables.")
        if key in self._bindings:
            raise ValueError(f"A callable is already bound for {key!r}.")
        self._bindings[key] = function

    def resolve(self, key: CallableBindingKey) -> PluginCallable:
        try:
            return self._bindings[key]
        except KeyError as error:
            raise CallableBindingNotFound(key) from error
