# Application contract examples

These modules define immutable, framework-neutral values crossing use-case and port boundaries. They compose domain-owned identities, scopes, quantities, statuses, and failures; they never import adapters, plugin DTOs, pandas, serializers, delivery models, ports, or services.

## Module map

| Module | Owns |
|---|---|
| `datasets.py` | Dataset/ingestion bindings, loaded dataset handles, and application-owned `ParameterSet` |
| `execution.py` | Dataset-aware execution keys, occurrence selection, runtime dependencies, and causal statuses |
| `operations.py` | Scope, normalization, context, alignment, prepared upstream artifacts, and plugin-execution DTOs |
| `providers.py` | Plan/catalog/function-pack source requests and snapshots |
| `exports.py` | Presentation-owned request and explicit `ExportReceipt | ExportFailed` outcome |
| `policies.py` | Boundary, out-of-range, alignment, and normalization choices |
| `requests.py` | Stateless `ProcessingRequest` |
| `plans.py` | Serializable locks, mapped node specs, typed static graphs, named targets, validation results, closures, and `CompiledPlan` |
| `reports.py` | Authoritative result/instance records with scope ancestry and `ProcessOutcome` |
| `tables.py` | Opaque request-scoped `TableHandle` passed between adapters |

## Outcome boundary

```text
ProcessingRequest
       ↓
 ProcessOutcome
 ├── RequestRejected(failures)       # no ExecutionReport exists
 └── ExecutionCompleted(report)      # authoritative typed report
```

Request failures must be request-level domain failures. Accepted executions always return per-instance statuses, including failed and not-calculated branches. Unexpected system failures are raised by the service and are not normal outcome values.

Export has an independent outcome boundary: expected destination/projection failures return `ExportFailed`, while unexpected exporter failures remain raised. `PresentationUnitProfileId` belongs only to `ExportRequest`; canonical processing reports can be exported repeatedly without recalculation.

## Deliberate exclusions

`ProcessingRequest` contains dataset and parameter references, not paths, DataFrames, JSON dictionaries, uploads, or source mappings. It selects calculation policies, not presentation units. `CompiledPlan` stores only serializable runtime values, hashes, and its validated static `CompiledGraph`; callable resolution remains an adapter responsibility. Contracts contain no loading, scheduling, or processing behavior.
