"""Mapping GraphQL schema configurations"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final, NamedTuple, TypedDict, cast

from ..pyutils import inspect, merge_kwargs
from ..type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLUnionType,
    introspection_types,
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_introspection_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_specified_directive,
    is_specified_scalar_type,
    is_union_type,
    specified_scalar_types,
)

if TYPE_CHECKING:
    from ..type import (
        GraphQLArgumentKwargs,
        GraphQLDirectiveKwargs,
        GraphQLEnumTypeKwargs,
        GraphQLEnumValueKwargs,
        GraphQLFieldKwargs,
        GraphQLInputFieldKwargs,
        GraphQLInputObjectTypeKwargs,
        GraphQLInterfaceTypeKwargs,
        GraphQLObjectTypeKwargs,
        GraphQLScalarTypeKwargs,
        GraphQLSchemaKwargs,
        GraphQLUnionTypeKwargs,
    )

__all__ = [
    "ConfigMapperMap",
    "MappedSchemaContext",
    "SchemaElementKind",
    "map_schema_config",
]


class SchemaElementKind:
    """The set of GraphQL Schema Elements."""

    SCHEMA: Final = "SCHEMA"
    SCALAR: Final = "SCALAR"
    OBJECT: Final = "OBJECT"
    FIELD: Final = "FIELD"
    ARGUMENT: Final = "ARGUMENT"
    INTERFACE: Final = "INTERFACE"
    UNION: Final = "UNION"
    ENUM: Final = "ENUM"
    ENUM_VALUE: Final = "ENUM_VALUE"
    INPUT_OBJECT: Final = "INPUT_OBJECT"
    INPUT_FIELD: Final = "INPUT_FIELD"
    DIRECTIVE: Final = "DIRECTIVE"


class MappedSchemaContext(NamedTuple):
    """Context provided to the configuration mappers."""

    get_named_type: Callable[[str], GraphQLNamedType]
    set_named_type: Callable[[GraphQLNamedType], None]
    get_named_types: Callable[[], tuple[GraphQLNamedType, ...]]


ScalarTypeConfigMapper = Callable[
    ["GraphQLScalarTypeKwargs"], "GraphQLScalarTypeKwargs"
]

ObjectTypeConfigMapper = Callable[
    ["GraphQLObjectTypeKwargs"], "GraphQLObjectTypeKwargs"
]

FieldConfigMapper = Callable[["GraphQLFieldKwargs", str], "GraphQLFieldKwargs"]

ArgumentConfigMapper = Callable[
    ["GraphQLArgumentKwargs", str, "str | None"], "GraphQLArgumentKwargs"
]

InterfaceTypeConfigMapper = Callable[
    ["GraphQLInterfaceTypeKwargs"], "GraphQLInterfaceTypeKwargs"
]

UnionTypeConfigMapper = Callable[["GraphQLUnionTypeKwargs"], "GraphQLUnionTypeKwargs"]

EnumTypeConfigMapper = Callable[["GraphQLEnumTypeKwargs"], "GraphQLEnumTypeKwargs"]

EnumValueConfigMapper = Callable[
    ["GraphQLEnumValueKwargs", str, str], "GraphQLEnumValueKwargs"
]

InputObjectTypeConfigMapper = Callable[
    ["GraphQLInputObjectTypeKwargs"], "GraphQLInputObjectTypeKwargs"
]

InputFieldConfigMapper = Callable[
    ["GraphQLInputFieldKwargs", str, str], "GraphQLInputFieldKwargs"
]

DirectiveConfigMapper = Callable[["GraphQLDirectiveKwargs"], "GraphQLDirectiveKwargs"]

SchemaConfigMapper = Callable[["GraphQLSchemaKwargs"], "GraphQLSchemaKwargs"]


class ConfigMapperMap(TypedDict, total=False):
    """A mapping of schema element kinds to their configuration mappers."""

    SCALAR: ScalarTypeConfigMapper
    OBJECT: ObjectTypeConfigMapper
    FIELD: FieldConfigMapper
    ARGUMENT: ArgumentConfigMapper
    INTERFACE: InterfaceTypeConfigMapper
    UNION: UnionTypeConfigMapper
    ENUM: EnumTypeConfigMapper
    ENUM_VALUE: EnumValueConfigMapper
    INPUT_OBJECT: InputObjectTypeConfigMapper
    INPUT_FIELD: InputFieldConfigMapper
    DIRECTIVE: DirectiveConfigMapper
    SCHEMA: SchemaConfigMapper


def map_schema_config(
    schema_config: GraphQLSchemaKwargs,
    config_mapper_map_fn: Callable[[MappedSchemaContext], ConfigMapperMap],
) -> GraphQLSchemaKwargs:
    """Map a schema configuration using the given configuration mappers.

    :meta private:
    """
    mapped_type_map: dict[str, GraphQLNamedType] = {}

    def get_type(
        type_: GraphQLList | GraphQLNonNull | GraphQLNamedType,
    ) -> GraphQLList | GraphQLNonNull | GraphQLNamedType:
        if is_list_type(type_):
            return GraphQLList(get_type(type_.of_type))
        if is_non_null_type(type_):
            return GraphQLNonNull(get_type(type_.of_type))
        return get_named_type(cast("GraphQLNamedType", type_).name)

    def get_named_type(type_name: str) -> GraphQLNamedType:
        type_ = std_type_map.get(type_name)
        if type_ is None:
            type_ = mapped_type_map.get(type_name)
        if type_ is None:  # pragma: no cover
            msg = f"Unknown type: '{type_name}'."
            raise TypeError(msg)
        return type_

    def set_named_type(type_: GraphQLNamedType) -> None:
        mapped_type_map[type_.name] = type_

    def get_named_types() -> tuple[GraphQLNamedType, ...]:
        return tuple(mapped_type_map.values())

    def map_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_introspection_type(type_) or is_specified_scalar_type(type_):
            # Builtin types cannot be mapped.
            return type_
        if is_scalar_type(type_):
            return map_scalar_type(type_)
        if is_object_type(type_):
            return map_object_type(type_)
        if is_interface_type(type_):
            return map_interface_type(type_)
        if is_union_type(type_):
            return map_union_type(type_)
        if is_enum_type(type_):
            return map_enum_type(type_)
        if is_input_object_type(type_):
            return map_input_object_type(type_)
        # Not reachable, all possible type definition nodes have been considered.
        msg = f"Unexpected type: {inspect(type_)}."  # pragma: no cover
        raise TypeError(msg)  # pragma: no cover

    def map_scalar_type(type_: GraphQLScalarType) -> GraphQLScalarType:
        mapped_config = type_.to_kwargs()
        mapper = config_mapper_map.get(SchemaElementKind.SCALAR)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return GraphQLScalarType(**mapped_config)

    def map_object_type(type_: GraphQLObjectType) -> GraphQLObjectType:
        config = type_.to_kwargs()
        mapped_config = merge_kwargs(
            config,
            interfaces=lambda: [
                cast("GraphQLInterfaceType", get_named_type(iface.name))
                for iface in config["interfaces"]
            ],
            fields=lambda: map_fields(config["fields"], type_.name),
        )
        mapper = config_mapper_map.get(SchemaElementKind.OBJECT)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return GraphQLObjectType(**mapped_config)

    def map_fields(
        field_map: dict[str, GraphQLField], parent_type_name: str
    ) -> dict[str, GraphQLField]:
        new_field_map = {}
        mapper = config_mapper_map.get(SchemaElementKind.FIELD)
        for field_name, field in field_map.items():
            mapped_field = merge_kwargs(
                field.to_kwargs(),
                type_=get_type(cast("GraphQLNamedType", field.type)),
                args=map_args(field.args, parent_type_name, field_name),
            )
            if mapper is not None:
                mapped_field = mapper(mapped_field, parent_type_name)
            new_field_map[field_name] = GraphQLField(**mapped_field)
        return new_field_map

    def map_args(
        argument_map: dict[str, GraphQLArgument],
        field_or_directive_name: str,
        parent_type_name: str | None = None,
    ) -> dict[str, GraphQLArgument]:
        new_argument_map = {}
        mapper = config_mapper_map.get(SchemaElementKind.ARGUMENT)
        for arg_name, arg in argument_map.items():
            mapped_arg = merge_kwargs(
                arg.to_kwargs(), type_=get_type(cast("GraphQLNamedType", arg.type))
            )
            if mapper is not None:
                mapped_arg = mapper(
                    mapped_arg, field_or_directive_name, parent_type_name
                )
            new_argument_map[arg_name] = GraphQLArgument(**mapped_arg)
        return new_argument_map

    def map_interface_type(type_: GraphQLInterfaceType) -> GraphQLInterfaceType:
        config = type_.to_kwargs()
        mapped_config = merge_kwargs(
            config,
            interfaces=lambda: [
                cast("GraphQLInterfaceType", get_named_type(iface.name))
                for iface in config["interfaces"]
            ],
            fields=lambda: map_fields(config["fields"], type_.name),
        )
        mapper = config_mapper_map.get(SchemaElementKind.INTERFACE)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return GraphQLInterfaceType(**mapped_config)

    def map_union_type(type_: GraphQLUnionType) -> GraphQLUnionType:
        config = type_.to_kwargs()
        mapped_config = merge_kwargs(
            config,
            types=lambda: [
                cast("GraphQLObjectType", get_named_type(member_type.name))
                for member_type in config["types"]
            ],
        )
        mapper = config_mapper_map.get(SchemaElementKind.UNION)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return GraphQLUnionType(**mapped_config)

    def map_enum_type(type_: GraphQLEnumType) -> GraphQLEnumType:
        config = type_.to_kwargs()

        def values() -> dict[str, GraphQLEnumValue]:
            new_enum_values = {}
            for value_name, value in config["values"].items():
                new_enum_values[value_name] = map_enum_value(
                    value, value_name, type_.name
                )
            return new_enum_values

        mapped_config = merge_kwargs(config, values=values)
        mapper = config_mapper_map.get(SchemaElementKind.ENUM)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return GraphQLEnumType(**mapped_config)

    def map_enum_value(
        value: GraphQLEnumValue, value_name: str, enum_name: str
    ) -> GraphQLEnumValue:
        mapped_config = value.to_kwargs()
        mapper = config_mapper_map.get(SchemaElementKind.ENUM_VALUE)
        if mapper is not None:
            mapped_config = mapper(mapped_config, value_name, enum_name)
        return GraphQLEnumValue(**mapped_config)

    def map_input_object_type(
        type_: GraphQLInputObjectType,
    ) -> GraphQLInputObjectType:
        config = type_.to_kwargs()

        def fields() -> dict[str, GraphQLInputField]:
            new_input_field_map = {}
            for field_name, field in config["fields"].items():
                new_input_field_map[field_name] = map_input_field(
                    field, field_name, type_.name
                )
            return new_input_field_map

        mapped_config = merge_kwargs(config, fields=fields)
        mapper = config_mapper_map.get(SchemaElementKind.INPUT_OBJECT)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return GraphQLInputObjectType(**mapped_config)

    def map_input_field(
        field: GraphQLInputField, input_field_name: str, input_object_type_name: str
    ) -> GraphQLInputField:
        mapped_config = merge_kwargs(
            field.to_kwargs(), type_=get_type(cast("GraphQLNamedType", field.type))
        )
        mapper = config_mapper_map.get(SchemaElementKind.INPUT_FIELD)
        if mapper is not None:
            mapped_config = mapper(
                mapped_config, input_field_name, input_object_type_name
            )
        return GraphQLInputField(**mapped_config)

    def map_directive(config: GraphQLDirectiveKwargs) -> GraphQLDirectiveKwargs:
        mapped_config = merge_kwargs(
            config, args=map_args(config["args"], config["name"], None)
        )
        mapper = config_mapper_map.get(SchemaElementKind.DIRECTIVE)
        if mapper is not None:
            mapped_config = mapper(mapped_config)
        return mapped_config

    config_mapper_map = config_mapper_map_fn(
        MappedSchemaContext(get_named_type, set_named_type, get_named_types)
    )

    for type_ in schema_config["types"] or ():
        mapped_type_map[type_.name] = map_named_type(type_)

    mapped_directives: list[GraphQLDirective] = []
    for directive in schema_config["directives"]:
        if is_specified_directive(directive):
            # Builtin directives cannot be mapped.
            mapped_directives.append(directive)
            continue
        mapped_directives.append(
            GraphQLDirective(**map_directive(directive.to_kwargs()))
        )

    query, mutation = schema_config["query"], schema_config["mutation"]
    subscription = schema_config["subscription"]
    mapped_schema_config = merge_kwargs(
        schema_config,
        query=cast("GraphQLObjectType", get_named_type(query.name)) if query else None,
        mutation=cast("GraphQLObjectType", get_named_type(mutation.name))
        if mutation
        else None,
        subscription=cast("GraphQLObjectType", get_named_type(subscription.name))
        if subscription
        else None,
        types=tuple(mapped_type_map.values()),
        directives=tuple(mapped_directives),
    )

    schema_mapper = config_mapper_map.get(SchemaElementKind.SCHEMA)
    return (
        mapped_schema_config
        if schema_mapper is None
        else schema_mapper(mapped_schema_config)
    )


std_type_map: dict[str, GraphQLNamedType] = {
    **specified_scalar_types,
    **introspection_types,
}
