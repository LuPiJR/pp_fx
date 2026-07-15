from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrakePowerConfiguration:
    efficiency: float = 1.0


@dataclass(frozen=True, slots=True)
class BrakeWindowConfiguration:
    opening_pressure_bar: float
    closing_pressure_bar: float

    def __post_init__(self) -> None:
        if self.closing_pressure_bar > self.opening_pressure_bar:
            raise ValueError("Closing pressure must not exceed opening pressure.")


@dataclass(frozen=True, slots=True)
class MeanConfiguration:
    include_failed_occurrences: bool = False
