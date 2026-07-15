# Opaque pandas table boundary

This adapter example keeps pandas available to concrete data-processing code without exposing a `DataFrame` through domain or application contracts.

## Ownership

```text
application service
    |
    | LoadedDataset / TableHandle / PreparedNodeInput
    v
scope, alignment, and plugin ports
    |
    | resolve only inside concrete adapters
    v
request-scoped PandasTableWorkspace
    |
    +-- canonical DataFrame values
    +-- node-local defensive copies
```

`TableHandle` remains an application-owned opaque token. `TableWorkspace` is an adapter-local interface and may therefore mention `pandas.DataFrame`. A handle resolves only in the workspace that created it and only while that workspace is live.

The composition root owns one workspace per synchronous request:

```python
with PandasTableWorkspace() as workspace:
    # Build the dataset gateway, scope resolver, aligner, and plugin executor
    # with this same workspace, then invoke ProcessDataset.
    ...
```

The context exit disposes tables after either normal return (`ExecutionCompleted` or `RequestRejected`) and after a raised system failure. Disposal is idempotent; a disposed workspace cannot be reused.

## Boundary examples

- `gateway.py` copies a registered external frame into workspace ownership and returns only `LoadedDataset` metadata plus a handle.
- `processing.py` implements application-facing scope/alignment signatures. It resolves handles internally and delegates algorithms to pandas kernel protocols; no interpolation or alignment algorithm is supplied here.
- `plugins.py` creates defensive node-local copies for every dataset role. The invocation seam never receives the canonical shared frame. A table-producing invocation must return an explicit frame, which becomes a `ProducedTableArtifact` with a new handle.
- `workspace.py` owns registration, lookup, isolation, and deterministic cleanup behavior.

## Deliberate omissions

No reader, normalization, interpolation, context expansion, alignment algorithm, unit conversion, callable discovery, scalar plugin mapping, mutation fingerprinting, performance optimization, or use-case orchestration appears here. The real pandas dependency is test-only because these executable examples remain outside the production wheel.
