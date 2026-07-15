from __future__ import annotations

from dataclasses import dataclass

from ..plugin_api.references import ChannelRef


@dataclass(frozen=True, slots=True)
class _VehicleChannels:
    speed: ChannelRef = ChannelRef("vehicle.speed")
    wheel_speed_front_left: ChannelRef = ChannelRef(
        "vehicle.wheel_speed.front_left"
    )


@dataclass(frozen=True, slots=True)
class _BrakeChannels:
    pressure_front_left: ChannelRef = ChannelRef(
        "vehicle.brake_pressure.front_left"
    )


@dataclass(frozen=True, slots=True)
class _DerivedChannels:
    brake_power_front_left: ChannelRef = ChannelRef(
        "example.braking.brake_power.front_left"
    )


vehicle = _VehicleChannels()
brake = _BrakeChannels()
derived = _DerivedChannels()
