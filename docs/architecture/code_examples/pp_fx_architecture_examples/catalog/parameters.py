from __future__ import annotations

from dataclasses import dataclass

from ..plugin_api.references import ParameterRef


@dataclass(frozen=True, slots=True)
class _GeometryParameters:
    wheel_radius_front_left: ParameterRef = ParameterRef(
        "vehicle.geometry.wheel_radius.front_left"
    )


geometry = _GeometryParameters()
