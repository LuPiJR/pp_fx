from __future__ import annotations

from dataclasses import dataclass

from .references import QuantityRef, UnitRef


@dataclass(frozen=True, slots=True)
class _Quantities:
    pressure: QuantityRef = QuantityRef("pressure")
    speed: QuantityRef = QuantityRef("speed")
    angular_speed: QuantityRef = QuantityRef("angular_speed")
    length: QuantityRef = QuantityRef("length")
    power: QuantityRef = QuantityRef("power")
    ratio: QuantityRef = QuantityRef("ratio")


quantities = _Quantities()


@dataclass(frozen=True, slots=True)
class _Units:
    bar: UnitRef = UnitRef("bar", quantities.pressure)
    metre_per_second: UnitRef = UnitRef("m/s", quantities.speed)
    revolution_per_minute: UnitRef = UnitRef("rpm", quantities.angular_speed)
    metre: UnitRef = UnitRef("m", quantities.length)
    kilowatt: UnitRef = UnitRef("kW", quantities.power)
    percent: UnitRef = UnitRef("percent", quantities.ratio)


units = _Units()
