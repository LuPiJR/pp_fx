from __future__ import annotations

from typing import TYPE_CHECKING

from ..catalog.channels import brake
from ..plugin_api.contracts import (
    ChannelRequirement,
    KpiInput,
    ScalarResult,
    ScalarResultDefinition,
)
from ..plugin_api.decorators import kpi
from ..plugin_api.units import units

if TYPE_CHECKING:
    import pandas as pd


@kpi(
    id="example.braking.maximum_pressure",
    requires_channels=(
        ChannelRequirement(brake.pressure_front_left, unit=units.bar),
    ),
    output=ScalarResultDefinition(
        artifact="example.braking.maximum_pressure",
        quantity=units.bar.quantity,
        unit=units.bar,
    ),
)
def maximum_brake_pressure(
    data: KpiInput[None, "pd.DataFrame"],
) -> ScalarResult:
    """Signature-only example; calculation behavior is deliberately omitted."""
    raise NotImplementedError


@kpi(
    id="example.braking.unexported_diagnostic",
    output=ScalarResultDefinition(
        artifact="example.braking.unexported_diagnostic",
        quantity=units.percent.quantity,
        unit=units.percent,
    ),
)
def unexported_diagnostic(
    data: KpiInput[None, "pd.DataFrame"],
) -> ScalarResult:
    """Decorated deliberately, proving decoration is not registration."""
    raise NotImplementedError
