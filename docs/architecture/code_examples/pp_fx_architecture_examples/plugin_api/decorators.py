from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import is_dataclass
from typing import ParamSpec, TypeVar, cast

from .contracts import (
    ChannelRequirement,
    ContextRequirement,
    DatasetRequirement,
    DerivedChannelDefinition,
    NodeDeclaration,
    NodeKind,
    ParameterRequirement,
    ResultRequirement,
    ScalarResultDefinition,
    WindowResultDefinition,
)

Parameters = ParamSpec("Parameters")
ReturnT = TypeVar("ReturnT")
PluginFunction = Callable[Parameters, ReturnT]
_DECLARATION_ATTRIBUTE = "__pp_fx_node_declaration__"


def _decorate(
    *,
    id: str,
    kind: NodeKind,
    requires_channels: tuple[ChannelRequirement, ...],
    requires_parameters: tuple[ParameterRequirement, ...],
    requires_datasets: tuple[DatasetRequirement, ...],
    requires_results: tuple[ResultRequirement, ...],
    context: ContextRequirement,
    configuration: type[object] | None,
    output: DerivedChannelDefinition | WindowResultDefinition | ScalarResultDefinition,
) -> Callable[[PluginFunction[Parameters, ReturnT]], PluginFunction[Parameters, ReturnT]]:
    if configuration is not None:
        dataclass_parameters = getattr(configuration, "__dataclass_params__", None)
        if (
            not isinstance(configuration, type)
            or not is_dataclass(configuration)
            or dataclass_parameters is None
            or not dataclass_parameters.frozen
        ):
            raise TypeError("Node configuration must be a frozen dataclass type.")

    def decorate(
        function: PluginFunction[Parameters, ReturnT],
    ) -> PluginFunction[Parameters, ReturnT]:
        signature = inspect.signature(function)
        parameters = tuple(signature.parameters.values())
        if len(parameters) != 1 or parameters[0].name != "data":
            raise TypeError("A plugin node must accept exactly one parameter named 'data'.")
        if parameters[0].annotation is inspect.Parameter.empty:
            raise TypeError("The plugin input parameter must be annotated.")
        if signature.return_annotation is inspect.Signature.empty:
            raise TypeError("A plugin node return type must be annotated.")
        if hasattr(function, _DECLARATION_ATTRIBUTE):
            raise TypeError("A plugin node cannot be decorated more than once.")

        declaration = NodeDeclaration(
            id=id,
            kind=kind,
            function_name=function.__name__,
            requires_channels=requires_channels,
            requires_parameters=requires_parameters,
            requires_datasets=requires_datasets,
            requires_results=requires_results,
            context=context,
            configuration=configuration,
            output=output,
        )
        setattr(function, _DECLARATION_ATTRIBUTE, declaration)
        return function

    return decorate


def derived_channel(
    *,
    id: str,
    output: DerivedChannelDefinition,
    requires_channels: tuple[ChannelRequirement, ...] = (),
    requires_parameters: tuple[ParameterRequirement, ...] = (),
    requires_datasets: tuple[DatasetRequirement, ...] = (),
    context: ContextRequirement = ContextRequirement(),
    configuration: type[object] | None = None,
) -> Callable[[PluginFunction[Parameters, ReturnT]], PluginFunction[Parameters, ReturnT]]:
    return _decorate(
        id=id,
        kind=NodeKind.DERIVED_CHANNEL,
        requires_channels=requires_channels,
        requires_parameters=requires_parameters,
        requires_datasets=requires_datasets,
        requires_results=(),
        context=context,
        configuration=configuration,
        output=output,
    )


def window_detector(
    *,
    id: str,
    output: WindowResultDefinition,
    requires_channels: tuple[ChannelRequirement, ...] = (),
    requires_parameters: tuple[ParameterRequirement, ...] = (),
    requires_datasets: tuple[DatasetRequirement, ...] = (),
    context: ContextRequirement = ContextRequirement(),
    configuration: type[object] | None = None,
) -> Callable[[PluginFunction[Parameters, ReturnT]], PluginFunction[Parameters, ReturnT]]:
    return _decorate(
        id=id,
        kind=NodeKind.WINDOW_DETECTOR,
        requires_channels=requires_channels,
        requires_parameters=requires_parameters,
        requires_datasets=requires_datasets,
        requires_results=(),
        context=context,
        configuration=configuration,
        output=output,
    )


def kpi(
    *,
    id: str,
    output: ScalarResultDefinition,
    requires_channels: tuple[ChannelRequirement, ...] = (),
    requires_parameters: tuple[ParameterRequirement, ...] = (),
    requires_datasets: tuple[DatasetRequirement, ...] = (),
    context: ContextRequirement = ContextRequirement(),
    configuration: type[object] | None = None,
) -> Callable[[PluginFunction[Parameters, ReturnT]], PluginFunction[Parameters, ReturnT]]:
    return _decorate(
        id=id,
        kind=NodeKind.KPI,
        requires_channels=requires_channels,
        requires_parameters=requires_parameters,
        requires_datasets=requires_datasets,
        requires_results=(),
        context=context,
        configuration=configuration,
        output=output,
    )


def metric(
    *,
    id: str,
    output: ScalarResultDefinition,
    requires_results: tuple[ResultRequirement, ...],
    configuration: type[object] | None = None,
) -> Callable[[PluginFunction[Parameters, ReturnT]], PluginFunction[Parameters, ReturnT]]:
    return _decorate(
        id=id,
        kind=NodeKind.METRIC,
        requires_channels=(),
        requires_parameters=(),
        requires_datasets=(),
        requires_results=requires_results,
        context=ContextRequirement(),
        configuration=configuration,
        output=output,
    )


def node_declaration(function: Callable[..., object]) -> NodeDeclaration:
    try:
        declaration = getattr(function, _DECLARATION_ATTRIBUTE)
    except AttributeError as error:
        raise TypeError(f"{function!r} is not a decorated plugin node.") from error
    return cast(NodeDeclaration, declaration)
