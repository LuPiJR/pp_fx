"""Typed example tables for mapping application and export outcomes outward."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from ..application.contracts.exports import ExportFailed, ExportOutcome, ExportReceipt
from ..application.contracts.reports import (
    ProcessOutcome,
    ReportStatus,
    RequestRejected,
)


class CliExitCode(IntEnum):
    SUCCESS = 0
    PARTIAL_SUCCESS = 10
    PROCESSING_FAILED = 11
    REQUEST_REJECTED = 20
    SYSTEM_FAILURE = 70
    EXPORT_FAILURE = 71


class GrpcStatusCode(StrEnum):
    OK = "OK"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INTERNAL = "INTERNAL"
    FAILED_PRECONDITION = "FAILED_PRECONDITION"


@dataclass(frozen=True, slots=True)
class CliOutcomeMapping:
    exit_code: CliExitCode
    report_status: ReportStatus | None
    failure_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GrpcOutcomeMapping:
    code: GrpcStatusCode
    report_status: ReportStatus | None
    failure_codes: tuple[str, ...]


_CLI_COMPLETED = {
    ReportStatus.SUCCESS: CliExitCode.SUCCESS,
    ReportStatus.PARTIAL_SUCCESS: CliExitCode.PARTIAL_SUCCESS,
    ReportStatus.FAILED: CliExitCode.PROCESSING_FAILED,
}


def map_process_outcome_to_cli(outcome: ProcessOutcome) -> CliOutcomeMapping:
    if isinstance(outcome, RequestRejected):
        return CliOutcomeMapping(
            CliExitCode.REQUEST_REJECTED,
            None,
            tuple(failure.code for failure in outcome.failures),
        )
    return CliOutcomeMapping(
        _CLI_COMPLETED[outcome.report.status],
        outcome.report.status,
        (),
    )


def map_process_outcome_to_grpc(outcome: ProcessOutcome) -> GrpcOutcomeMapping:
    if isinstance(outcome, RequestRejected):
        return GrpcOutcomeMapping(
            GrpcStatusCode.INVALID_ARGUMENT,
            None,
            tuple(failure.code for failure in outcome.failures),
        )
    return GrpcOutcomeMapping(
        GrpcStatusCode.OK,
        outcome.report.status,
        (),
    )


def map_system_failure_to_cli(error: Exception) -> CliOutcomeMapping:
    _ = error
    return CliOutcomeMapping(
        CliExitCode.SYSTEM_FAILURE,
        None,
        ("SYSTEM_FAILURE",),
    )


def map_system_failure_to_grpc(error: Exception) -> GrpcOutcomeMapping:
    _ = error
    return GrpcOutcomeMapping(
        GrpcStatusCode.INTERNAL,
        None,
        ("SYSTEM_FAILURE",),
    )


def map_export_outcome_to_cli(outcome: ExportOutcome) -> CliOutcomeMapping:
    if isinstance(outcome, ExportReceipt):
        return CliOutcomeMapping(CliExitCode.SUCCESS, None, ())
    return CliOutcomeMapping(
        CliExitCode.EXPORT_FAILURE,
        None,
        (outcome.code,),
    )


def map_export_outcome_to_grpc(outcome: ExportOutcome) -> GrpcOutcomeMapping:
    if isinstance(outcome, ExportFailed):
        return GrpcOutcomeMapping(
            GrpcStatusCode.FAILED_PRECONDITION,
            None,
            (outcome.code,),
        )
    return GrpcOutcomeMapping(GrpcStatusCode.OK, None, ())
