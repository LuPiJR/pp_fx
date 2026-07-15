from __future__ import annotations

from ..plugin_api.contracts import (
    MetricInput,
    ResultRequirement,
    ScalarResult,
    ScalarResultDefinition,
)
from ..plugin_api.decorators import metric
from ..plugin_api.units import units
from .configuration import MeanConfiguration


@metric(
    id="example.braking.maximum_pressure.mean",
    requires_results=(
        ResultRequirement("example.braking.maximum_pressure"),
    ),
    configuration=MeanConfiguration,
    output=ScalarResultDefinition(
        artifact="example.braking.maximum_pressure.mean",
        quantity=units.bar.quantity,
        unit=units.bar,
    ),
)
def mean_maximum_brake_pressure(
    data: MetricInput[MeanConfiguration],
) -> ScalarResult:
    """Signature-only example; fan-in execution belongs to a later slice."""
    raise NotImplementedError
