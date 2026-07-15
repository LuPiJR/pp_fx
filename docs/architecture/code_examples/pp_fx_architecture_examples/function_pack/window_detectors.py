from __future__ import annotations

from typing import TYPE_CHECKING

from ..catalog.channels import brake
from ..plugin_api.contracts import (
    ChannelRequirement,
    ContextRequirement,
    WindowDetectionResult,
    WindowDetectorInput,
    WindowResultDefinition,
)
from ..plugin_api.decorators import window_detector
from ..plugin_api.units import units
from .configuration import BrakeWindowConfiguration

if TYPE_CHECKING:
    import pandas as pd


@window_detector(
    id="example.braking.windows",
    requires_channels=(
        ChannelRequirement(brake.pressure_front_left, unit=units.bar),
    ),
    context=ContextRequirement(before_samples=1, after_samples=1),
    configuration=BrakeWindowConfiguration,
    output=WindowResultDefinition(artifact="example.braking.windows"),
)
def brake_windows(
    data: WindowDetectorInput[BrakeWindowConfiguration, "pd.DataFrame"],
) -> WindowDetectionResult:
    """Signature-only example; detection belongs to a later architecture slice."""
    raise NotImplementedError
