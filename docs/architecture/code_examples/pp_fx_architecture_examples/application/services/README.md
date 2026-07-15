# Application service examples

## Static graph compiler

`graph_compiler.py` is a small educational compiler. It joins adapter-mapped `CompiledNodeSpec` values with plan-resolved typed artifact contracts, validates the complete static graph, and returns either a `CompiledGraph` or typed validation failures.

Compilation makes these decisions once:

- one producer or declared external source per artifact,
- matching producer/consumer artifact kinds,
- explicit scope behavior on every node dependency,
- unique named processing targets with valid exports,
- deterministic acyclic topological order.

`select_target_closure` projects a compiled graph to named targets and their transitive dependencies. It preserves compiled topological order and excludes independent branches. Processing examples can therefore consume the closure without inspecting plugin declarations or recalculating graph policy.

```text
mapped CompiledNodeSpec + typed artifacts + targets
                         ↓
              compile_static_graph
                  /             \
       validation failures    CompiledGraph
                                    ↓
                         select_target_closure
```

This example does not schedule execution, materialize occurrences, invoke plugins, cache values, run concurrently, or mutate a compiled plan.

## ProcessDataset orchestration

`process_dataset.py` demonstrates the synchronous input-port implementation and its dependency direction:

```text
driving adapter
      ↓
ProcessDataset.execute(ProcessingRequest)
      ↓
plan repository → request validation → target closure
      ↓
dataset/parameter gateways → normalization → scope → context → alignment
      ↓
sequential plugin port calls → dependency propagation → ExecutionReport
      ↓
RequestRejected | ExecutionCompleted
```

The service constructor receives only application protocols. It never creates an adapter, resolves a pandas frame, imports plugin DTOs, or manages callable bindings. A composition root may wrap the call in the request-scoped pandas workspace described by `adapters/pandas_tables/`.

Request-owned target/role errors return `RequestRejected` before plugin invocation. Plugin adapters return typed failed artifacts for expected node failures; the service records the failed instance, marks only descendants `NOT_CALCULATED`, and continues independent nodes. Unexpected exceptions and broken port invariants remain raised system failures.

This is a same-scope educational scheduler only. It omits occurrence fan-out/fan-in, boundary algorithms, context sufficiency policy, output trimming, timing/provenance enrichment, persistence, caching, concurrency, and resource-lifecycle composition.

## Detected-window occurrence scheduler

`occurrence_scheduler.py` is a separate pure materialization example connecting static scope-edge semantics to runtime instance data:

```text
detector@parent → completed windows + isolated occurrence issues
                         ↓ explicit selector
        EACH_SELECTED_CHILD_SCOPE
              ├── consumer@child/occurrence-1
              └── consumer@child/occurrence-2
                         ↓ explicit FAN_IN_SELECTED_CHILDREN
                    metric@parent
```

Every `ExecutionInstanceKey` includes node identity, canonical dataset fingerprints, scope identity, and optional occurrence identity. Complete windows become child instances; an incomplete trailing candidate remains an issue and does not block complete siblings. `require exactly one` produces a node-level cardinality failure and causal `NOT_CALCULATED` records only for descendants of that selector edge. Fan-in is rejected unless its compiled edge explicitly declares `FAN_IN_SELECTED_CHILDREN`.

The scheduler does not call plugins or mutate the compiled graph. It omits parallelism, streaming, retries, caching, optimized queues, and production orchestration integration.

## ExportReport separation

`export_report.py` implements the separate `ExportReport` input port by delegating one immutable `ExportRequest` to an injected `ReportExporter`. The service returns `ExportReceipt | ExportFailed`; it performs no projection, unit conversion, serialization, or writing itself.

`ProcessDatasetService` has no exporter dependency. A delivery command may optionally pass a completed report to `ExportReportService`, but calculation remains valid without that second use case. Unexpected exporter exceptions remain raised system failures.
