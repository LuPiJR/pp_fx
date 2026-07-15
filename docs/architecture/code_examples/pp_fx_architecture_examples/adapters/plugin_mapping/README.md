# Plugin anti-corruption mapping

This adapter is the only example boundary that understands both public plugin DTOs and inward runtime values. Neither side imports the other.

## Mapping flow

```text
plugin NodeDeclaration
+ locked FunctionPackLock
+ runtime RuntimeCatalogSnapshot
              |
              v
    PluginDeclarationMapper
       /               \
StaticValidationResult  CompiledNodeSpec
(mapping failures)      (runtime values only)
```

`RuntimeCatalogSnapshot` represents the already assembled, locked catalog view. It maps canonical channel and parameter values to runtime IDs, graph artifacts, quantity kinds, and units. Generated catalog `ChannelRef` and `ParameterRef` objects never enter the snapshot.

The mapper:

1. resolves plugin references by canonical value;
2. rejects unknown channels, parameters, quantities, and units;
3. checks unit declarations against runtime quantity dimensions;
4. converts requirements, context, output, and node kind into application-contract values;
5. returns either a plugin-free `CompiledNodeSpec` or explicit static mapping failures.

Expected mapping problems are values in `StaticValidationResult`. Direct `map_channel` and `map_parameter` helpers raise `ReferenceMappingError` carrying the same typed `MappingFailure` detail.

## Callable ownership

Callables remain adapter-owned and never enter `CompiledNodeSpec`:

```text
CallableBindingKey(
    pack_id,
    version,
    artifact_hash,
    declaration_hash,
    node_id,
) -> Python callable
```

`InMemoryCallableRegistry` demonstrates exact-key binding only. Changing either content hash prevents resolution. Resolving a callable is not invoking it; plugin execution belongs to a later adapter example.

## Deliberate omissions

No entry-point scanning, package installation, environment resolution, filesystem access, callable execution, pandas preparation, or plan orchestration appears here. This is executable architecture documentation, not a production registry or compiler.
