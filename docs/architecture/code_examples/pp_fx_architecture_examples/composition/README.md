# Composition-root walkthrough

> Architecture example only. This is not production bootstrap code or an implementation template.

`bootstrap.py` is the outermost module and the only example-package module that chooses concrete dependencies. It creates one composition per request, opens the pandas table workspace, constructs driven adapters and tracing decorators, binds one exact callable-registry key, injects all application ports, and exposes the Python driving facade.

## Chosen strategy

| Strategy | Benefit | Cost | Decision |
|---|---|---|---|
| Global container/service locator | Short call sites | Hidden dependencies, global lifecycle, difficult tests | Rejected |
| Long-lived application graph with mutable request state | Fewer constructions | Cross-request leakage risk | Rejected |
| Explicit request-scoped factory | Visible dependencies and deterministic cleanup | More wiring | Chosen |

The wiring is intentionally verbose. Constructor calls show technology ownership; the application service itself never imports or creates adapters.

## Request sequence

```text
compose_example_application
  → PandasTableWorkspace
  → fake repositories/gateways/preparation adapters
  → exact callable registry + registry-backed fake executor
  → ProcessDatasetService
  → PythonRequestBuilder
  → PythonProcessingFacade

ArchitectureExampleApplication.process
  → PythonProcessInput
  → ProcessingRequest
  → selected plan closure
  → opaque table preparation
  → canned scalar PluginExecutionResult
  → ExecutionCompleted

ArchitectureExampleApplication.__exit__
  → dispose request workspace
```

`CallTrace` records this boundary order. The unknown-target walkthrough stops after plan lookup and returns `RequestRejected`; no dataset or plugin adapter runs. A second request requires a second composition.

## Deliberate limits

The fixed frame and scalar result are explanatory fixtures. There is no real calculation, IO, plugin discovery, persistence, export, CLI/gRPC server, concurrency, streaming, deployment configuration, or production resource container.
