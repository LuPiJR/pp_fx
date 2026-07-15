# Application port examples

These focused `Protocol` interfaces describe capabilities required by application services. They import only standard-library typing and application contract DTOs. No port selects pandas, a filesystem, package entry points, CLI tooling, serialization, or an exporter library.

## Module map

| Module | Capabilities |
|---|---|
| `gateways.py` | Load bound datasets and parameters; retrieve compiled plans |
| `processing.py` | Normalize data, resolve scopes, expand context, and align datasets |
| `plugins.py` | Execute one immutable compiled node against prepared input |
| `providers.py` | Resolve plan, catalog, and function-pack source snapshots |
| `exports.py` | Project/write an authoritative report through an injected driven port |
| `use_cases.py` | Drive independent `ProcessDataset` and `ExportReport` use cases |

All protocols are runtime-checkable because the executable contract tests intentionally verify structural conformance. Concrete adapters do not need to inherit from them.

```text
application.services -> application.ports -> application.contracts -> domain
concrete adapters ----------------^ 
```

`adapters/fakes.py` provides deterministic canned implementations for service examples. `adapters/recording.py` wraps those protocols with one shared call trace, making orchestration order visible without entering the service. These adapters contain no processing logic or framework objects. `adapters/pandas_tables/` demonstrates concrete dataset, scope, alignment, and plugin boundaries sharing an adapter-owned request workspace while these port signatures remain unchanged. Production adapters may use pandas, package metadata, files, or external stores without changing services.
