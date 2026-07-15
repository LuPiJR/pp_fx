from __future__ import annotations

from ..plugin_api.function_pack import CatalogRequirement, FunctionPackDefinition
from .derived_channels import brake_power
from .kpis import maximum_brake_pressure
from .metrics import mean_maximum_brake_pressure
from .window_detectors import brake_windows


FUNCTION_PACK = FunctionPackDefinition(
    id="example.braking",
    version="1.0.0",
    plugin_api_version=">=1,<2",
    catalog_requirements=(
        CatalogRequirement(id="example.standard", version_range=">=1,<2"),
    ),
    nodes=(
        brake_power,
        brake_windows,
        maximum_brake_pressure,
        mean_maximum_brake_pressure,
    ),
)
