from __future__ import annotations

from typing import TYPE_CHECKING

from ..catalog.channels import brake, derived, vehicle
from ..catalog.parameters import geometry
from ..plugin_api.contracts import (
    ChannelRequirement,
    ContextRequirement,
    DerivedChannelDefinition,
    DerivedChannelInput,
    ParameterRequirement,
)
from ..plugin_api.decorators import derived_channel
from ..plugin_api.units import units
from .configuration import BrakePowerConfiguration

if TYPE_CHECKING:
    import pandas as pd


@derived_channel(
    id="example.braking.brake_power.front_left",
    requires_channels=(
        ChannelRequirement(brake.pressure_front_left, unit=units.bar),
        ChannelRequirement(
            vehicle.wheel_speed_front_left,
            unit=units.revolution_per_minute,
        ),
    ),
    requires_parameters=(
        ParameterRequirement(geometry.wheel_radius_front_left, unit=units.metre),
    ),
    context=ContextRequirement(before_samples=1, after_samples=1),
    configuration=BrakePowerConfiguration,
    output=DerivedChannelDefinition(
        channel=derived.brake_power_front_left,
        quantity=units.kilowatt.quantity,
        unit=units.kilowatt,
    ),
)
def brake_power(
    data: DerivedChannelInput[BrakePowerConfiguration, "pd.DataFrame"],
) -> "pd.Series":
    """Signature-only example; the architecture set does not implement formulas."""
    raise NotImplementedError
