"""Runtime-owned canonical identifiers.

External strings are parsed into these values at a boundary. Distinct classes prevent a
channel identifier from being passed where an artifact or node identifier is required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CANONICAL_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_ROLE = re.compile(r"^[a-z][a-z0-9_]*$")
_OPAQUE_REFERENCE = re.compile(r"^[^\s]+$")


@dataclass(frozen=True, slots=True)
class _CanonicalId:
    value: str

    def __post_init__(self) -> None:
        if not _CANONICAL_ID.fullmatch(self.value):
            raise ValueError(
                "A canonical ID must contain at least two lowercase dot-separated "
                "segments; each segment must start with a letter."
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class _RoleValue:
    value: str

    def __post_init__(self) -> None:
        if not _ROLE.fullmatch(self.value):
            raise ValueError("A role must be one lowercase identifier segment.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class _OpaqueReference:
    value: str

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(self.value):
            raise ValueError("A reference must be non-empty and contain no whitespace.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ChannelId(_CanonicalId):
    """Canonical sampled-channel identity owned by the runtime domain."""


@dataclass(frozen=True, slots=True)
class ParameterId(_CanonicalId):
    """Canonical non-sampled parameter identity owned by the runtime domain."""


@dataclass(frozen=True, slots=True)
class ScopeId(_CanonicalId):
    """Identity of a requested or resolved processing scope."""


@dataclass(frozen=True, slots=True)
class ArtifactId(_CanonicalId):
    """Identity of a typed artifact consumed or produced by a graph node."""


@dataclass(frozen=True, slots=True)
class CalculationNodeId(_CanonicalId):
    """Identity of a calculation declaration in the static graph."""


@dataclass(frozen=True, slots=True)
class PlanId(_CanonicalId):
    """Identity of a reusable processing-plan definition."""


@dataclass(frozen=True, slots=True)
class CompiledPlanId(_CanonicalId):
    """Identity of an immutable compiled processing plan."""


@dataclass(frozen=True, slots=True)
class ProcessingTargetId(_CanonicalId):
    """Identity of a public calculation bundle exposed by a plan."""


@dataclass(frozen=True, slots=True)
class FunctionPackId(_CanonicalId):
    """Identity of an installed function-pack declaration."""


@dataclass(frozen=True, slots=True)
class CatalogId(_CanonicalId):
    """Identity of a versioned channel or parameter catalog."""


@dataclass(frozen=True, slots=True)
class ExecutionInstanceId(_CanonicalId):
    """Identity of one node execution in one resolved scope."""


@dataclass(frozen=True, slots=True)
class OccurrenceId(_CanonicalId):
    """Identity of one detected child-window occurrence."""


@dataclass(frozen=True, slots=True)
class DatasetRole(_RoleValue):
    """Semantic role of a named dataset binding."""


@dataclass(frozen=True, slots=True)
class DatasetReference(_OpaqueReference):
    """Transport-neutral reference resolved by a dataset gateway."""


@dataclass(frozen=True, slots=True)
class IngestionProfileReference(_CanonicalId):
    """Identity of a versioned source mapping and reader profile."""


@dataclass(frozen=True, slots=True)
class ParameterSetReference(_OpaqueReference):
    """Transport-neutral reference resolved by a parameter gateway."""
