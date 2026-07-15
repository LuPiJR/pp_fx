# Delivery boundary examples

These modules translate external values into application contracts and application outcomes back into transport policy. They own no processing, graph, unit-conversion, export-format, or storage algorithms.

## Request mapping

```text
PythonProcessInput ──> PythonRequestBuilder ─┐
                                             ├──> ProcessingRequest
JsonProcessRequestV1 -> JsonRequestMapperV1 ┘
future protobuf message -> FutureGrpcRequestMapper[T] signature only
```

`request_dtos.py` owns immutable external shapes. `request_mapping.py` parses every identifier, policy, decimal, axis, and unit explicitly. `RequestValueCatalog` is injected so transport aliases do not enter domain values. Invalid external values raise `DeliveryMappingError` with a stable path and code before the application input port is invoked.

The JSON DTO has an explicit `pp-fx.process-request/v1` schema version. JSON parsing and schema-framework integration remain outside this example. The Python facade accepts `Decimal` magnitudes to avoid silently introducing binary-float values.

`PythonProcessingFacade` only builds the shared request and invokes `ProcessDataset`. It has no exporter dependency.

## Outcome mapping

`outcome_mapping.py` encodes the illustrative mapping table as typed functions:

| Boundary result | CLI exit | gRPC status | Report retained |
|---|---:|---|---|
| `ExecutionCompleted(SUCCESS)` | `SUCCESS` | `OK` | yes |
| `ExecutionCompleted(PARTIAL_SUCCESS)` | `PARTIAL_SUCCESS` | `OK` | yes |
| `ExecutionCompleted(FAILED)` | `PROCESSING_FAILED` | `OK` | yes |
| `RequestRejected` | `REQUEST_REJECTED` | `INVALID_ARGUMENT` | no |
| raised system failure | `SYSTEM_FAILURE` | `INTERNAL` | no |
| `ExportFailed` | `EXPORT_FAILURE` | `FAILED_PRECONDITION` | unrelated |

Completed failed reports remain successful gRPC transport responses because node failures are report data, not transport failures. System exceptions are mapped only by the driving edge and are not converted into `ProcessOutcome`.

## Export separation

```text
ProcessDataset -> ExecutionCompleted(report)
                         |
                         | optional, separate command/use case
                         v
ExportReportService -> ReportExporter -> ExportReceipt | ExportFailed
```

`ExportRequest` is the only request containing `PresentationUnitProfileId`. Processing remains canonical and can succeed without any exporter. Expected exporter failures are explicit values; unexpected exporter/system exceptions remain raised.

## Deliberate limits

No raw-dictionary parser, CLI framework, gRPC server, generated protobuf type, JSON schema library, filesystem writer, report serializer, unit-conversion algorithm, or concrete exporter is implemented here.
