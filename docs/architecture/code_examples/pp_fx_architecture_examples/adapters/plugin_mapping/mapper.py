"""Anti-corruption mapper from public plugin DTOs to runtime-owned specifications."""

from __future__ import annotations

from ...application.contracts.plans import (
    CompiledChannelInput,
    CompiledContext,
    CompiledDatasetInput,
    CompiledNodeKind,
    CompiledNodeSpec,
    CompiledOutput,
    CompiledParameterInput,
    FunctionPackLock,
    NodeConfigurationEntry,
)
from ...domain.identifiers import (
    ArtifactId,
    CalculationNodeId,
    ChannelId,
    DatasetRole,
    ParameterId,
)
from ...domain.units import QuantityKind, Unit
from ...plugin_api.contracts import (
    ChannelRequirement,
    DatasetRequirement,
    DerivedChannelDefinition,
    NodeDeclaration,
    ParameterRequirement,
    ResultRequirement,
    ScalarResultDefinition,
    WindowResultDefinition,
)
from ...plugin_api.references import ChannelRef, ParameterRef, QuantityRef, UnitRef
from .catalog import ChannelDefinition, ParameterDefinition, RuntimeCatalogSnapshot
from .validation import (
    MappingFailure,
    MappingFailureCode,
    NodeMappingResult,
    StaticValidationResult,
)


class ReferenceMappingError(ValueError):
    def __init__(self, failure: MappingFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)


class PluginDeclarationMapper:
    """Maps by canonical value and rejects unknown or incompatible references."""

    def __init__(self, catalog: RuntimeCatalogSnapshot) -> None:
        self._channels = {definition.id.value: definition for definition in catalog.channels}
        self._parameters = {
            definition.id.value: definition for definition in catalog.parameters
        }
        self._units = {unit.symbol: unit for unit in catalog.units}
        quantity_kinds = (
            *(definition.quantity_kind for definition in catalog.channels),
            *(definition.quantity_kind for definition in catalog.parameters),
            *(unit.quantity_kind for unit in catalog.units),
        )
        self._quantity_kinds = {
            quantity_kind.value: quantity_kind for quantity_kind in quantity_kinds
        }

    def map_channel(self, reference: ChannelRef) -> ChannelId:
        return self._channel_definition(reference).id

    def map_parameter(self, reference: ParameterRef) -> ParameterId:
        return self._parameter_definition(reference).id

    def map_declaration(
        self,
        declaration: NodeDeclaration,
        *,
        pack: FunctionPackLock,
        configuration: tuple[NodeConfigurationEntry, ...] = (),
    ) -> NodeMappingResult:
        channel_inputs, channel_artifacts, channel_failures = (
            self._map_channel_inputs(declaration.requires_channels)
        )
        parameter_inputs, parameter_artifacts, parameter_failures = (
            self._map_parameter_inputs(declaration.requires_parameters)
        )
        dataset_inputs, dataset_artifacts, dataset_failures = (
            self._map_dataset_inputs(declaration.requires_datasets)
        )
        result_artifacts, result_failures = self._map_result_inputs(
            declaration.requires_results
        )
        output, output_failures = self._validated_output(declaration)
        node_id, node_failures = self._validated_node_id(declaration.id)
        validation = StaticValidationResult(
            (
                *channel_failures,
                *parameter_failures,
                *dataset_failures,
                *result_failures,
                *output_failures,
                *node_failures,
            )
        )

        if not validation.is_valid:
            return NodeMappingResult(specification=None, validation=validation)
        if output is None or node_id is None:
            raise RuntimeError("A valid plugin mapping lost required runtime values.")

        try:
            specification = CompiledNodeSpec(
                id=node_id,
                pack=pack,
                consumes=(
                    *channel_artifacts,
                    *parameter_artifacts,
                    *dataset_artifacts,
                    *result_artifacts,
                ),
                produces=(output.artifact,),
                configuration=configuration,
                kind=CompiledNodeKind(declaration.kind.value),
                channel_inputs=channel_inputs,
                parameter_inputs=parameter_inputs,
                dataset_inputs=dataset_inputs,
                context=CompiledContext(
                    before_samples=declaration.context.before_samples,
                    after_samples=declaration.context.after_samples,
                ),
                output=output,
            )
        except (TypeError, ValueError) as error:
            failure = self._failure(
                MappingFailureCode.INVALID_DECLARATION,
                declaration.id,
                str(error),
            )
            return NodeMappingResult(
                specification=None,
                validation=StaticValidationResult((failure,)),
            )

        return NodeMappingResult(
            specification=specification,
            validation=StaticValidationResult(),
        )

    def _map_channel_inputs(
        self,
        requirements: tuple[ChannelRequirement, ...],
    ) -> tuple[
        tuple[CompiledChannelInput, ...],
        tuple[ArtifactId, ...],
        tuple[MappingFailure, ...],
    ]:
        inputs: list[CompiledChannelInput] = []
        artifacts: list[ArtifactId] = []
        failures: list[MappingFailure] = []
        for requirement in requirements:
            try:
                definition = self._channel_definition(requirement.channel)
                unit = self._optional_compatible_unit(
                    requirement.unit,
                    definition.quantity_kind,
                    requirement.channel.value,
                )
                inputs.append(
                    CompiledChannelInput(
                        channel=definition.id,
                        artifact=definition.artifact,
                        calculation_unit=unit,
                        required=requirement.required,
                    )
                )
                artifacts.append(definition.artifact)
            except ReferenceMappingError as error:
                failures.append(error.failure)
        return tuple(inputs), tuple(artifacts), tuple(failures)

    def _map_parameter_inputs(
        self,
        requirements: tuple[ParameterRequirement, ...],
    ) -> tuple[
        tuple[CompiledParameterInput, ...],
        tuple[ArtifactId, ...],
        tuple[MappingFailure, ...],
    ]:
        inputs: list[CompiledParameterInput] = []
        artifacts: list[ArtifactId] = []
        failures: list[MappingFailure] = []
        for requirement in requirements:
            try:
                definition = self._parameter_definition(requirement.parameter)
                unit = self._optional_compatible_unit(
                    requirement.unit,
                    definition.quantity_kind,
                    requirement.parameter.value,
                )
                inputs.append(
                    CompiledParameterInput(
                        parameter=definition.id,
                        artifact=definition.artifact,
                        calculation_unit=unit,
                        required=requirement.required,
                    )
                )
                artifacts.append(definition.artifact)
            except ReferenceMappingError as error:
                failures.append(error.failure)
        return tuple(inputs), tuple(artifacts), tuple(failures)

    def _map_dataset_inputs(
        self,
        requirements: tuple[DatasetRequirement, ...],
    ) -> tuple[
        tuple[CompiledDatasetInput, ...],
        tuple[ArtifactId, ...],
        tuple[MappingFailure, ...],
    ]:
        inputs: list[CompiledDatasetInput] = []
        artifacts: list[ArtifactId] = []
        failures: list[MappingFailure] = []
        for requirement in requirements:
            try:
                axis = self._channel_definition(requirement.axis)
                inputs.append(
                    CompiledDatasetInput(
                        role=DatasetRole(requirement.role),
                        axis=axis.id,
                        axis_artifact=axis.artifact,
                        required=requirement.required,
                    )
                )
                artifacts.append(axis.artifact)
            except ReferenceMappingError as error:
                failures.append(error.failure)
            except ValueError as error:
                failures.append(
                    self._failure(
                        MappingFailureCode.INVALID_IDENTIFIER,
                        requirement.role,
                        str(error),
                    )
                )
        return tuple(inputs), tuple(artifacts), tuple(failures)

    def _map_result_inputs(
        self,
        requirements: tuple[ResultRequirement, ...],
    ) -> tuple[tuple[ArtifactId, ...], tuple[MappingFailure, ...]]:
        artifacts: list[ArtifactId] = []
        failures: list[MappingFailure] = []
        for requirement in requirements:
            try:
                artifacts.append(self._artifact_id(requirement.artifact))
            except ReferenceMappingError as error:
                failures.append(error.failure)
        return tuple(artifacts), tuple(failures)

    def _validated_output(
        self,
        declaration: NodeDeclaration,
    ) -> tuple[CompiledOutput | None, tuple[MappingFailure, ...]]:
        try:
            return self._map_output(declaration.output), ()
        except ReferenceMappingError as error:
            return None, (error.failure,)

    def _validated_node_id(
        self,
        value: str,
    ) -> tuple[CalculationNodeId | None, tuple[MappingFailure, ...]]:
        try:
            return CalculationNodeId(value), ()
        except ValueError as error:
            failure = self._failure(
                MappingFailureCode.INVALID_IDENTIFIER,
                value,
                str(error),
            )
            return None, (failure,)

    def _channel_definition(self, reference: ChannelRef) -> ChannelDefinition:
        try:
            return self._channels[reference.value]
        except KeyError as error:
            failure = self._failure(
                MappingFailureCode.UNKNOWN_CHANNEL,
                reference.value,
                f"Unknown runtime channel {reference.value!r}.",
            )
            raise ReferenceMappingError(failure) from error

    def _parameter_definition(self, reference: ParameterRef) -> ParameterDefinition:
        try:
            return self._parameters[reference.value]
        except KeyError as error:
            failure = self._failure(
                MappingFailureCode.UNKNOWN_PARAMETER,
                reference.value,
                f"Unknown runtime parameter {reference.value!r}.",
            )
            raise ReferenceMappingError(failure) from error

    def _quantity_kind(self, reference: QuantityRef) -> QuantityKind:
        try:
            return self._quantity_kinds[reference.value]
        except KeyError as error:
            failure = self._failure(
                MappingFailureCode.UNKNOWN_QUANTITY,
                reference.value,
                f"Unknown runtime quantity {reference.value!r}.",
            )
            raise ReferenceMappingError(failure) from error

    def _compatible_unit(
        self,
        reference: UnitRef,
        expected_quantity: QuantityKind,
        owner_reference: str,
    ) -> Unit:
        try:
            unit = self._units[reference.value]
        except KeyError as error:
            failure = self._failure(
                MappingFailureCode.UNKNOWN_UNIT,
                reference.value,
                f"Unknown runtime unit {reference.value!r}.",
            )
            raise ReferenceMappingError(failure) from error

        declared_quantity = self._quantity_kind(reference.quantity)
        if unit.quantity_kind != declared_quantity:
            raise ReferenceMappingError(
                self._failure(
                    MappingFailureCode.UNIT_QUANTITY_MISMATCH,
                    reference.value,
                    "The plugin unit reference disagrees with the runtime unit quantity.",
                )
            )
        if declared_quantity != expected_quantity:
            raise ReferenceMappingError(
                self._failure(
                    MappingFailureCode.INCOMPATIBLE_DIMENSION,
                    owner_reference,
                    "The required calculation unit is dimensionally incompatible.",
                )
            )
        return unit

    def _optional_compatible_unit(
        self,
        reference: UnitRef | None,
        expected_quantity: QuantityKind,
        owner_reference: str,
    ) -> Unit | None:
        if reference is None:
            return None
        return self._compatible_unit(reference, expected_quantity, owner_reference)

    def _map_output(
        self,
        output: DerivedChannelDefinition | WindowResultDefinition | ScalarResultDefinition,
    ) -> CompiledOutput:
        if isinstance(output, DerivedChannelDefinition):
            channel = self._channel_definition(output.channel)
            quantity_kind = self._quantity_kind(output.quantity)
            if channel.quantity_kind != quantity_kind:
                raise ReferenceMappingError(
                    self._failure(
                        MappingFailureCode.INCOMPATIBLE_DIMENSION,
                        output.channel.value,
                        "The produced channel quantity disagrees with its declaration.",
                    )
                )
            unit = self._compatible_unit(
                output.unit,
                quantity_kind,
                output.channel.value,
            )
            return CompiledOutput(channel.artifact, quantity_kind, unit)

        if isinstance(output, ScalarResultDefinition):
            quantity_kind = self._quantity_kind(output.quantity)
            unit = self._compatible_unit(
                output.unit,
                quantity_kind,
                output.artifact,
            )
            return CompiledOutput(
                self._artifact_id(output.artifact),
                quantity_kind,
                unit,
            )

        if isinstance(output, WindowResultDefinition):
            return CompiledOutput(self._artifact_id(output.artifact))

        raise ReferenceMappingError(
            self._failure(
                MappingFailureCode.INVALID_DECLARATION,
                type(output).__name__,
                "Unsupported plugin output declaration.",
            )
        )

    def _artifact_id(self, value: str) -> ArtifactId:
        try:
            return ArtifactId(value)
        except ValueError as error:
            failure = self._failure(
                MappingFailureCode.INVALID_IDENTIFIER,
                value,
                str(error),
            )
            raise ReferenceMappingError(failure) from error

    @staticmethod
    def _failure(
        code: MappingFailureCode,
        reference: str,
        message: str,
    ) -> MappingFailure:
        return MappingFailure(code=code, reference=reference, message=message)
