# Typed architecture examples

## Purpose

This directory is the executable companion to the accepted `pp-fx` architecture documentation. Its modules illustrate boundary ownership, dependency direction, and connections between Clean Architecture layers. They are intentionally small teaching examples, not production runtime code or implementation templates.

The example package lives under `docs/`, outside `src/`. It is not part of the `pp-fx` distribution and production code must not import it. Pytest makes it importable only while running the documentation contract tests.

## Layout

```text
code_examples/
├── pp_fx_architecture_examples/
│   ├── domain/
│   │   └── windows.py
│   ├── application/
│   │   ├── contracts/
│   │   │   ├── datasets.py
│   │   │   ├── execution.py
│   │   │   ├── exports.py
│   │   │   ├── operations.py
│   │   │   ├── plans.py
│   │   │   ├── policies.py
│   │   │   ├── providers.py
│   │   │   ├── reports.py
│   │   │   ├── requests.py
│   │   │   └── tables.py
│   │   ├── ports/
│   │   │   ├── exports.py
│   │   │   ├── gateways.py
│   │   │   ├── plugins.py
│   │   │   ├── processing.py
│   │   │   ├── providers.py
│   │   │   └── use_cases.py
│   │   └── services/
│   │       ├── export_report.py
│   │       ├── graph_compiler.py
│   │       ├── occurrence_scheduler.py
│   │       └── process_dataset.py
│   ├── plugin_api/
│   │   ├── references.py
│   │   ├── contracts.py
│   │   ├── decorators.py
│   │   ├── function_pack.py
│   │   └── units.py
│   ├── catalog/
│   ├── function_pack/
│   ├── adapters/
│   │   ├── fakes.py
│   │   ├── recording.py
│   │   ├── pandas_tables/
│   │   │   ├── gateway.py
│   │   │   ├── plugins.py
│   │   │   ├── processing.py
│   │   │   └── workspace.py
│   │   └── plugin_mapping/
│   │       ├── catalog.py
│   │       ├── mapper.py
│   │       ├── registry.py
│   │       └── validation.py
│   ├── delivery/
│   │   ├── outcome_mapping.py
│   │   ├── python_facade.py
│   │   ├── request_dtos.py
│   │   └── request_mapping.py
│   └── composition/
│       └── bootstrap.py
└── tests/
```

Dependencies point inward:

```text
composition -> delivery/adapters -> application.services
application.services -> application.ports -> application.contracts -> domain
plugin_api <- sample catalog/function-pack examples
adapters -> plugin_api + inward runtime examples
```

No package initializer re-exports another layer. Examples import their exact owner module so dependency direction remains visible. [`INDEX.md`](INDEX.md) maps every executable module to the architecture documents and visual overview.

## Application contract slice

`application.contracts` composes domain-owned values into immutable dataset/parameter bindings, processing requests, compiled-plan shapes, execution reports, and the explicit `RequestRejected | ExecutionCompleted` outcome. `ParameterSet` is application-owned; its IDs and typed values remain domain-owned. `TableHandle` is an opaque token rather than a DataFrame. Contracts import only domain modules, standard-library modules, and sibling contracts.

The request deliberately excludes paths, JSON dictionaries, pandas objects, plugin DTOs, source mappings, and presentation units. Compiled plans deliberately exclude callables. No loading, orchestration, or execution behavior appears in this slice.

## Application port slice

`application.ports` defines focused structural protocols for gateways, compiled-plan storage, normalization, scope/context/alignment preparation, plugin execution, artifact providers, and report export. Every signature uses application contract DTOs; no port imports domain owners directly or chooses a framework.

`adapters.fakes` supplies deterministic in-memory/canned implementations with call recording. These fakes prove protocol conformance and support later service examples without introducing pandas, filesystems, CLI frameworks, package discovery, or concrete exporters.

## Compiled graph slice

`domain.graph` owns typed artifact kinds, inputs/outputs, and explicit `SAME_SCOPE`, `EACH_SELECTED_CHILD_SCOPE`, and `FAN_IN_SELECTED_CHILDREN` edge semantics. `application.services.graph_compiler` combines these values with adapter-mapped `CompiledNodeSpec` values and named `ProcessingTarget` exports.

Compilation returns typed static validation failures for missing or duplicate producers, contract mismatches, invalid targets, and cycles. Successful graphs have deterministic topological order. Target selection returns only the transitive dependency closure, so independent unselected branches never reach processing. This educational compiler contains no scheduling, caching, concurrency, occurrence fan-out, or plugin invocation.

## ProcessDataset service slice

`application.services.process_dataset.ProcessDatasetService` implements the `ProcessDataset` input port using only injected repository, gateway, preparation, alignment, and plugin-execution protocols. It validates target/role selection, prepares opaque table handles, executes the selected same-scope closure sequentially, passes successful intermediate artifacts forward, and assembles an authoritative `ExecutionCompleted` report.

Unknown request targets and missing required dataset roles become `RequestRejected` before plugin execution. Typed plugin failures remain node-instance failures and block only graph descendants; independent nodes continue. Unexpected port or invariant failures are never caught and remain raised to the driving adapter. `adapters.recording` supplies technology-free tracing decorators that make the demonstrated call order explicit.

## Detected-window fan-out slice

`domain.windows` represents complete detected windows as resolved child scopes while retaining candidate-specific issues such as `INCOMPLETE_WINDOW`. `application.contracts.execution` adds dataset-aware `ExecutionInstanceKey` values, explicit occurrence selectors, materialized runtime dependencies, and causal blocked-instance records.

`application.services.occurrence_scheduler` selects completed occurrences and interprets compiled scope-edge policy. `EACH_SELECTED_CHILD_SCOPE` creates one consumer key per selected child; `FAN_IN_SELECTED_CHILDREN` creates one parent consumer only through that explicit edge. Cardinality failure blocks only the selector edge's runtime descendants. Incomplete candidates remain reportable issues and do not invalidate completed siblings. Result records retain complete scope ancestry and occurrence identity.

This deterministic example materializes execution data only. It does not invoke plugins, stream windows, run concurrently, optimize schedules, or replace the deliberately same-scope `ProcessDatasetService` skeleton.

## Delivery and export slice

`delivery` owns versioned Python/JSON input shapes, explicit value mapping, and typed CLI/gRPC outcome policies. Both driving paths create the same `ProcessingRequest`; invalid external IDs, policies, axes, units, or decimal values become path-specific `DeliveryMappingError` values before invocation. Future protobuf integration is represented only by a generic mapper protocol.

Processing and export remain independent use cases. `ExportReportService` delegates an `ExportRequest` to `ReportExporter` and returns `ExportReceipt | ExportFailed`. Presentation-unit selection exists only on the export request; `PythonProcessingFacade` requires no exporter.

## Plugin API slice

The plugin example keeps three separate owners:

- `plugin_api` defines immutable author references, requirements, input/output DTOs, decorators, and the explicit pack manifest.
- `catalog` models a generated namespace package whose values are plugin-owned references.
- `function_pack` shows derived-channel, window-detector, KPI, and metric declarations without implementing calculations.

Decorators attach a frozen `NodeDeclaration` directly to a callable. They preserve the callable signature and never register globally. `FunctionPackDefinition.nodes` is the sole export list. Function packs and catalog modules import the plugin API but never runtime domain, application, adapter, delivery, or composition modules. Runtime mapping, discovery, orchestration, and calculations belong to later examples.

## Plugin mapping adapter slice

`adapters.plugin_mapping` is the anti-corruption boundary between public plugin declarations and inward runtime values. It resolves plugin references against a runtime-owned catalog snapshot, validates dimensions, and returns either explicit static mapping failures or a serializable `CompiledNodeSpec` containing no plugin DTO or callable.

The callable registry is an adapter-local protocol keyed by exact pack ID, version, distribution hash, declaration hash, and node ID. Hash mismatches cannot resolve a callable. This slice performs no package discovery, environment resolution, plugin execution, or plan orchestration.

## Pandas table adapter slice

`adapters.pandas_tables` owns one request-scoped workspace of canonical pandas frames. Application services and ports see only `TableHandle` values. Dataset, scope, alignment, and plugin adapters share the workspace and resolve handles internally.

Scope and alignment algorithms remain injected kernel protocols. Plugin preparation creates defensive node-local copies and returns explicit table artifacts under new handles. The workspace context disposes every frame after successful completion, request rejection, or a raised system failure. Pandas is a development dependency solely for these executable adapter fixtures; the examples remain outside the production wheel.

## Composition-root and end-to-end slice

`composition.bootstrap` is the only example module that constructs concrete adapters. It creates one request-scoped pandas workspace, canned gateways/resolvers, an exact callable registry and fake executor, tracing decorators, `ProcessDatasetService`, request mapper, and `PythonProcessingFacade`.

The success walkthrough maps one external in-memory request through the complete port sequence into a scalar `ExecutionCompleted` report. The rejection walkthrough changes only the target and stops after plan lookup. The composition context always disposes its workspace. This is deliberately explicit wiring—not a global container, production bootstrap, calculation implementation, or deployment template.

See [`INDEX.md`](INDEX.md) for the dependency diagram, module map, HTML slide links, call sequence, and recommended reading/test order.

## Conventions

### Naming

- Modules and local variables use `snake_case`.
- Values, entities, DTOs, and protocols use descriptive `PascalCase` nouns.
- Protocol names describe capabilities, such as `DatasetGateway`; no `I` prefix.
- Methods use verbs that state one operation, such as `load`, `resolve`, or `execute`.
- Runtime-owned types and plugin-facing types keep distinct names and modules even when their serialized values match.

### Type annotations

- Annotate every public class attribute, parameter, and return value.
- Prefer precise unions and immutable collections over `Any` and mutable containers.
- Use `T | None` only when absence is part of the contract.
- Keep framework types out of domain and application-facing annotations.
- Avoid stringly typed internal values; parse strings into validated value objects at boundaries.

### Immutability

- Use `@dataclass(frozen=True, slots=True)` for value objects and DTOs.
- Prefer tuples and frozensets for owned collections.
- Validate invariants in constructors; do not expose partially valid values.
- Keep execution state outside compiled plans and reusable declarations.

### Protocols

- Define `typing.Protocol` interfaces in the consuming boundary.
- Keep each protocol focused on the behavior required by its use case.
- Accept and return boundary-owned typed contracts, never concrete adapter types.
- Use structural typing rather than inheritance from adapter base classes.
- Add `@runtime_checkable` only when runtime `isinstance` checks are an explicit requirement.

## Contract tests

From the `pp_fx` project root:

```bash
uv run pytest
```

The scaffold tests validate syntax, import every example module, confirm that the examples remain outside production source, and reject production imports of the documentation package. Later examples add focused contract tests beside this harness.

Static type-checker selection remains an accepted deferred architecture decision. Once the project selects one, its `uv run` command and architecture-example paths must be added here and to the project quality gate; this scaffold does not invent a second type-checking policy.
