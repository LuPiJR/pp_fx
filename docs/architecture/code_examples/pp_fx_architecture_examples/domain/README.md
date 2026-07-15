# Domain examples

These modules outline the innermost `pp-fx` policy. They use only the Python standard library and know nothing about application services, pandas, plugin-facing references, delivery DTOs, serializers, or file IO.

## Module map

| Module | Owns | Key invariant |
|---|---|---|
| `identifiers.py` | Runtime channel, parameter, scope, artifact, plan, target, dataset, pack, catalog, and execution identities | Canonical IDs and opaque gateway references remain validated, distinct Python types. |
| `units.py` | `QuantityKind`, `Unit`, and `Quantity` | A finite numeric magnitude never crosses a domain boundary without a unit. |
| `scopes.py` | `CoordinateAxis`, requested/effective bounds, boundary mode, and ancestry | Bounds have one compatible quantity/unit; child scopes stay inside their parent. |
| `failures.py` | Request, node, and system failure categories plus failure detail | Failure codes and messages are explicit values; system failures are classified but remain raised by application services. |
| `results.py` | Artifact status, value, provenance, and failure relationships | Success requires a typed value and provenance; failure states carry only node-level failure detail. |
| `graph.py` | Typed artifact inputs/outputs, external sources, dependency edges, and scope-edge modes | Every edge names its artifact kind and runtime scope relationship; a node cannot directly depend on itself. |
| `windows.py` | Complete detected child windows, detection results, and candidate-specific occurrence issues | Completed and incomplete occurrence identities are disjoint; every child or issue retains its detector parent scope. |

## Connection to outer layers

Application contracts import these values to define requests, reports, and compiled specifications:

```text
application.contracts -> domain
```

The dependency never reverses. Plugin API references intentionally remain separate types and are mapped by an adapter in a later example.

## Illustrative relationship

```python
from decimal import Decimal

from pp_fx_architecture_examples.domain.identifiers import ChannelId, ScopeId
from pp_fx_architecture_examples.domain.scopes import (
    BoundaryMode,
    CoordinateAxis,
    RequestedScope,
    ResolvedScope,
)
from pp_fx_architecture_examples.domain.units import Quantity, QuantityKind, Unit


distance = QuantityKind("distance")
metre = Unit("si.metre", "m", distance)
axis = CoordinateAxis(ChannelId("lap.distance"), distance, metre)
requested = RequestedScope(
    id=ScopeId("scope.sector_two"),
    axis=axis,
    start=Quantity(Decimal("500"), metre),
    end=Quantity(Decimal("700"), metre),
)
resolved = ResolvedScope(
    requested=requested,
    effective_start=requested.start,
    effective_end=requested.end,
    boundary_mode=BoundaryMode.EXACT,
)
```

This is executable documentation, not production implementation. It deliberately omits conversion engines, graph scheduling, orchestration, DataFrames, persistence, and transport mapping.
