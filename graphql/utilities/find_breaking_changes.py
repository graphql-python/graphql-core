from enum import Enum
from typing import List, NamedTuple, Union, cast

from ..error import INVALID
from ..pyutils import inspect
from ..type import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    GraphQLUnionType,
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_list_type,
    is_named_type,
    is_required_argument,
    is_required_input_field,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_union_type,
)

__all__ = [
    "BreakingChange",
    "BreakingChangeType",
    "DangerousChange",
    "DangerousChangeType",
    "find_breaking_changes",
    "find_dangerous_changes",
]


class BreakingChangeType(Enum):
    FIELD_CHANGED_KIND = 10
    FIELD_REMOVED = 11
    TYPE_CHANGED_KIND = 20
    TYPE_REMOVED = 21
    TYPE_REMOVED_FROM_UNION = 22
    VALUE_REMOVED_FROM_ENUM = 30
    ARG_REMOVED = 40
    ARG_CHANGED_KIND = 41
    REQUIRED_ARG_ADDED = 50
    REQUIRED_INPUT_FIELD_ADDED = 51
    INTERFACE_REMOVED_FROM_OBJECT = 60
    DIRECTIVE_REMOVED = 70
    DIRECTIVE_ARG_REMOVED = 71
    DIRECTIVE_LOCATION_REMOVED = 72
    REQUIRED_DIRECTIVE_ARG_ADDED = 73


class DangerousChangeType(Enum):
    ARG_DEFAULT_VALUE_CHANGE = 42
    VALUE_ADDED_TO_ENUM = 31
    INTERFACE_ADDED_TO_OBJECT = 61
    TYPE_ADDED_TO_UNION = 23
    OPTIONAL_INPUT_FIELD_ADDED = 52
    OPTIONAL_ARG_ADDED = 53


class BreakingChange(NamedTuple):
    type: BreakingChangeType
    description: str


class DangerousChange(NamedTuple):
    type: DangerousChangeType
    description: str


BreakingOrDangerousChange = Union[BreakingChange, DangerousChange]


def find_breaking_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find breaking changes.

    Given two schemas, returns a list containing descriptions of all the types of
    breaking changes covered by the other functions down below.
    """
    breaking_changes = [
        change
        for change in find_schema_changes(old_schema, new_schema)
        if isinstance(change.type, BreakingChangeType)
    ]
    return cast(List[BreakingChange], breaking_changes)


def find_dangerous_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    """Find dangerous changes.

    Given two schemas, returns a list containing descriptions of all the types of
    potentially dangerous changes covered by the other functions down below.
    """
    dangerous_changes = [
        change
        for change in find_schema_changes(old_schema, new_schema)
        if isinstance(change.type, DangerousChangeType)
    ]
    return cast(List[DangerousChange], dangerous_changes)


def find_schema_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingOrDangerousChange]:
    return [
        *find_removed_types(old_schema, new_schema),
        *find_types_that_changed_kind(old_schema, new_schema),
        *find_fields_that_changed_type_on_object_or_interface_types(
            old_schema, new_schema
        ),
        *find_fields_that_changed_type_on_input_object_types(old_schema, new_schema),
        *find_types_added_to_unions(old_schema, new_schema),
        *find_types_removed_from_unions(old_schema, new_schema),
        *find_values_added_to_enums(old_schema, new_schema),
        *find_values_removed_from_enums(old_schema, new_schema),
        *find_arg_changes(old_schema, new_schema),
        *find_interfaces_added_to_object_types(old_schema, new_schema),
        *find_interfaces_removed_from_object_types(old_schema, new_schema),
        *find_removed_directives(old_schema, new_schema),
        *find_removed_directive_args(old_schema, new_schema),
        *find_added_non_null_directive_args(old_schema, new_schema),
        *find_removed_directive_locations(old_schema, new_schema),
    ]


def find_removed_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find removed types.

    Given two schemas, returns a list containing descriptions of any breaking changes
    in the newSchema related to removing an entire type.
    """
    schema_changes: List[BreakingChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name in old_type_map:
        if type_name not in new_type_map:
            schema_changes.append(
                BreakingChange(
                    BreakingChangeType.TYPE_REMOVED, f"{type_name} was removed."
                )
            )
    return schema_changes


def find_types_that_changed_kind(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find types that changed kind

    Given two schemas, returns a list containing descriptions of any breaking changes
    in the newSchema related to changing the type of a type.
    """
    schema_changes: List[BreakingChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name in old_type_map:
        if type_name not in new_type_map:
            continue
        old_type = old_type_map[type_name]
        new_type = new_type_map[type_name]
        if old_type.__class__ is not new_type.__class__:
            schema_changes.append(
                BreakingChange(
                    BreakingChangeType.TYPE_CHANGED_KIND,
                    f"{type_name} changed from {type_kind_name(old_type)}"
                    f" to {type_kind_name(new_type)}.",
                )
            )
    return schema_changes


def find_arg_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingOrDangerousChange]:
    """Find argument changes.

    Given two schemas, returns a list containing descriptions of any breaking or
    dangerous changes in the new_schema related to arguments (such as removal or change
    of type of an argument, or a change in an argument's default value).
    """
    schema_changes: List[BreakingOrDangerousChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if (
            not (is_object_type(old_type) or is_interface_type(old_type))
            or not (is_object_type(new_type) or is_interface_type(new_type))
            or new_type.__class__ is not old_type.__class__
        ):
            continue
        old_type = cast(Union[GraphQLObjectType, GraphQLInterfaceType], old_type)
        new_type = cast(Union[GraphQLObjectType, GraphQLInterfaceType], new_type)

        old_fields = old_type.fields
        new_fields = new_type.fields
        for field_name in old_fields:
            if field_name not in new_fields:
                continue

            old_args = old_fields[field_name].args
            new_args = new_fields[field_name].args
            for arg_name, old_arg in old_args.items():
                new_arg = new_args.get(arg_name)
                if not new_arg:
                    # Arg not present
                    schema_changes.append(
                        BreakingChange(
                            BreakingChangeType.ARG_REMOVED,
                            f"{old_type.name}.{field_name} arg"
                            f" {arg_name} was removed.",
                        )
                    )
                    continue
                is_safe = is_change_safe_for_input_object_field_or_field_arg(
                    old_arg.type, new_arg.type
                )
                if not is_safe:
                    schema_changes.append(
                        BreakingChange(
                            BreakingChangeType.ARG_CHANGED_KIND,
                            f"{old_type.name}.{field_name} arg"
                            f" {arg_name} has changed type from"
                            f" {old_arg.type} to {new_arg.type}.",
                        )
                    )
                elif (
                    old_arg.default_value is not INVALID
                    and old_arg.default_value != new_arg.default_value
                ):
                    schema_changes.append(
                        DangerousChange(
                            DangerousChangeType.ARG_DEFAULT_VALUE_CHANGE,
                            f"{old_type.name}.{field_name} arg"
                            f" {arg_name} has changed defaultValue.",
                        )
                    )

            # Check if arg was added to the field
            for arg_name in new_args:
                if arg_name not in old_args:
                    if is_required_argument(new_args[arg_name]):
                        schema_changes.append(
                            BreakingChange(
                                BreakingChangeType.REQUIRED_ARG_ADDED,
                                f"A required arg {arg_name} on"
                                f" {type_name}.{field_name} was added.",
                            )
                        )
                    else:
                        schema_changes.append(
                            DangerousChange(
                                DangerousChangeType.OPTIONAL_ARG_ADDED,
                                f"An optional arg {arg_name} on"
                                f" {type_name}.{field_name} was added.",
                            )
                        )

    return schema_changes


def type_kind_name(type_: GraphQLNamedType) -> str:
    if is_scalar_type(type_):
        return "a Scalar type"
    if is_object_type(type_):
        return "an Object type"
    if is_interface_type(type_):
        return "an Interface type"
    if is_union_type(type_):
        return "a Union type"
    if is_enum_type(type_):
        return "an Enum type"
    if is_input_object_type(type_):
        return "an Input type"

    # Not reachable. All possible output types have been considered.
    raise TypeError(f"Unexpected type {inspect(type)}")  # pragma: no cover


def find_fields_that_changed_type_on_object_or_interface_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    schema_changes: List[BreakingChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if (
            not (is_object_type(old_type) or is_interface_type(old_type))
            or not (is_object_type(new_type) or is_interface_type(new_type))
            or new_type.__class__ is not old_type.__class__
        ):
            continue
        old_type = cast(Union[GraphQLObjectType, GraphQLInterfaceType], old_type)
        new_type = cast(Union[GraphQLObjectType, GraphQLInterfaceType], new_type)

        old_fields = old_type.fields
        new_fields = new_type.fields
        for field_name in old_fields:
            # Check if the field is missing on the type in the new schema.
            if field_name not in new_fields:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.FIELD_REMOVED,
                        f"{type_name}.{field_name} was removed.",
                    )
                )
            else:
                old_field_type = old_fields[field_name].type
                new_field_type = new_fields[field_name].type
                is_safe = is_change_safe_for_object_or_interface_field(
                    old_field_type, new_field_type
                )
                if not is_safe:
                    schema_changes.append(
                        BreakingChange(
                            BreakingChangeType.FIELD_CHANGED_KIND,
                            f"{type_name}.{field_name} changed type"
                            f" from {old_field_type}"
                            f" to {new_field_type}.",
                        )
                    )

    return schema_changes


def find_fields_that_changed_type_on_input_object_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingOrDangerousChange]:
    schema_changes: List[BreakingOrDangerousChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_input_object_type(old_type) and is_input_object_type(new_type)):
            continue
        old_type = cast(GraphQLInputObjectType, old_type)
        new_type = cast(GraphQLInputObjectType, new_type)

        old_fields = old_type.fields
        new_fields = new_type.fields
        for field_name in old_fields:
            # Check if the field is missing on the type in the new schema.
            if field_name not in new_fields:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.FIELD_REMOVED,
                        f"{type_name}.{field_name} was removed.",
                    )
                )
            else:
                old_field_type = old_fields[field_name].type
                new_field_type = new_fields[field_name].type
                is_safe = is_change_safe_for_input_object_field_or_field_arg(
                    old_field_type, new_field_type
                )
                if not is_safe:
                    schema_changes.append(
                        BreakingChange(
                            BreakingChangeType.FIELD_CHANGED_KIND,
                            f"{type_name}.{field_name} changed type"
                            f" from {old_field_type}"
                            f" to {new_field_type}.",
                        )
                    )

        # Check if a field was added to the input object type
        for field_name in new_fields:
            if field_name not in old_fields:
                if is_required_input_field(new_fields[field_name]):
                    schema_changes.append(
                        BreakingChange(
                            BreakingChangeType.REQUIRED_INPUT_FIELD_ADDED,
                            f"A required field {field_name} on"
                            f" input type {type_name} was added.",
                        )
                    )
                else:
                    schema_changes.append(
                        DangerousChange(
                            DangerousChangeType.OPTIONAL_INPUT_FIELD_ADDED,
                            f"An optional field {field_name} on"
                            f" input type {type_name} was added.",
                        )
                    )
    return schema_changes


def is_change_safe_for_object_or_interface_field(
    old_type: GraphQLType, new_type: GraphQLType
) -> bool:
    if is_list_type(old_type):
        return (
            # if they're both lists, make sure underlying types are compatible
            is_list_type(new_type)
            and is_change_safe_for_object_or_interface_field(
                cast(GraphQLList, old_type).of_type, cast(GraphQLList, new_type).of_type
            )
        ) or (
            # moving from nullable to non-null of same underlying type is safe
            is_non_null_type(new_type)
            and is_change_safe_for_object_or_interface_field(
                old_type, cast(GraphQLNonNull, new_type).of_type
            )
        )

    if is_non_null_type(old_type):
        # if they're both non-null, make sure underlying types are compatible
        return is_non_null_type(
            new_type
        ) and is_change_safe_for_object_or_interface_field(
            cast(GraphQLNonNull, old_type).of_type,
            cast(GraphQLNonNull, new_type).of_type,
        )

    return (
        # if they're both named types, see if their names are equivalent
        is_named_type(new_type)
        and cast(GraphQLNamedType, old_type).name
        == cast(GraphQLNamedType, new_type).name
    ) or (
        # moving from nullable to non-null of same underlying type is safe
        is_non_null_type(new_type)
        and is_change_safe_for_object_or_interface_field(
            old_type, cast(GraphQLNonNull, new_type).of_type
        )
    )


def is_change_safe_for_input_object_field_or_field_arg(
    old_type: GraphQLType, new_type: GraphQLType
) -> bool:
    if is_list_type(old_type):

        return is_list_type(
            # if they're both lists, make sure underlying types are compatible
            new_type
        ) and is_change_safe_for_input_object_field_or_field_arg(
            cast(GraphQLList, old_type).of_type, cast(GraphQLList, new_type).of_type
        )

    if is_non_null_type(old_type):
        return (
            # if they're both non-null, make sure the underlying types are compatible
            is_non_null_type(new_type)
            and is_change_safe_for_input_object_field_or_field_arg(
                cast(GraphQLNonNull, old_type).of_type,
                cast(GraphQLNonNull, new_type).of_type,
            )
        ) or (
            # moving from non-null to nullable of same underlying type is safe
            not is_non_null_type(new_type)
            and is_change_safe_for_input_object_field_or_field_arg(
                cast(GraphQLNonNull, old_type).of_type, new_type
            )
        )

    return (
        # if they're both named types, see if their names are equivalent
        is_named_type(new_type)
        and cast(GraphQLNamedType, old_type).name
        == cast(GraphQLNamedType, new_type).name
    )


def find_types_removed_from_unions(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find types removed from unions.

    Given two schemas, returns a list containing descriptions of any breaking changes
    in the new_schema related to removing types from a union type.
    """
    schema_changes: List[BreakingChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for old_type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(old_type_name)
        if not (is_union_type(old_type) and is_union_type(new_type)):
            continue
        old_type = cast(GraphQLUnionType, old_type)
        new_type = cast(GraphQLUnionType, new_type)
        new_possible_type_names = (type_.name for type_ in new_type.types)
        for old_possible_type in old_type.types:
            if old_possible_type.name not in new_possible_type_names:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.TYPE_REMOVED_FROM_UNION,
                        f"{old_possible_type.name} was removed"
                        f" from union type {old_type_name}.",
                    )
                )
    return schema_changes


def find_types_added_to_unions(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    """Find types added to union.

    Given two schemas, returns a list containing descriptions of any dangerous changes
    in the new_schema related to adding types to a union type.
    """
    schema_changes: List[DangerousChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for old_type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(old_type_name)
        if not (is_union_type(old_type) and is_union_type(new_type)):
            continue
        old_type = cast(GraphQLUnionType, old_type)
        new_type = cast(GraphQLUnionType, new_type)
        old_possible_type_names = {type_.name for type_ in old_type.types}
        for new_possible_type in new_type.types:
            if new_possible_type.name not in old_possible_type_names:
                schema_changes.append(
                    DangerousChange(
                        DangerousChangeType.TYPE_ADDED_TO_UNION,
                        f"{new_possible_type.name} was added"
                        f" to union type {old_type_name}.",
                    )
                )
    return schema_changes


def find_values_removed_from_enums(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find values removed from enums.

    Given two schemas, returns a list containing descriptions of any breaking changes
    in the new_schema related to removing values from an enum type.
    """
    schema_changes: List[BreakingChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_enum_type(old_type) and is_enum_type(new_type)):
            continue
        old_type = cast(GraphQLEnumType, old_type)
        new_type = cast(GraphQLEnumType, new_type)
        for value_name in old_type.values:
            if value_name not in new_type.values:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.VALUE_REMOVED_FROM_ENUM,
                        f"{value_name} was removed from enum type {type_name}.",
                    )
                )
    return schema_changes


def find_values_added_to_enums(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    """Find values added to enums.

    Given two schemas, returns a list containing descriptions of any dangerous changes
    in the new_schema related to adding values to an enum type.
    """
    schema_changes: List[DangerousChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_enum_type(old_type) and is_enum_type(new_type)):
            continue
        old_type = cast(GraphQLEnumType, old_type)
        new_type = cast(GraphQLEnumType, new_type)
        for value_name in new_type.values:
            if value_name not in old_type.values:
                schema_changes.append(
                    DangerousChange(
                        DangerousChangeType.VALUE_ADDED_TO_ENUM,
                        f"{value_name} was added to enum type {type_name}.",
                    )
                )
    return schema_changes


def find_interfaces_removed_from_object_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    schema_changes: List[BreakingChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_object_type(old_type) and is_object_type(new_type)):
            continue
        old_type = cast(GraphQLObjectType, old_type)
        new_type = cast(GraphQLObjectType, new_type)

        old_interfaces = old_type.interfaces
        new_interfaces = new_type.interfaces
        new_interface_names = {interface.name for interface in new_interfaces}
        for old_interface in old_interfaces:
            if old_interface.name not in new_interface_names:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.INTERFACE_REMOVED_FROM_OBJECT,
                        f"{type_name} no longer implements interface"
                        f" {old_interface.name}.",
                    )
                )
    return schema_changes


def find_interfaces_added_to_object_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    schema_changes: List[DangerousChange] = []

    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    for type_name, new_type in new_type_map.items():
        old_type = old_type_map.get(type_name)
        if not (is_object_type(old_type) and is_object_type(new_type)):
            continue
        old_type = cast(GraphQLObjectType, old_type)
        new_type = cast(GraphQLObjectType, new_type)

        old_interfaces = old_type.interfaces
        new_interfaces = new_type.interfaces
        old_interface_names = {interface.name for interface in old_interfaces}
        for new_interface in new_interfaces:
            if new_interface.name not in old_interface_names:
                schema_changes.append(
                    DangerousChange(
                        DangerousChangeType.INTERFACE_ADDED_TO_OBJECT,
                        f"{new_interface.name} added to interfaces implemented"
                        f" by {type_name}.",
                    )
                )
    return schema_changes


def find_removed_directives(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    schema_changes: List[BreakingChange] = []

    new_directives_names = {directive.name for directive in new_schema.directives}
    for old_directive in old_schema.directives:
        if old_directive.name not in new_directives_names:
            schema_changes.append(
                BreakingChange(
                    BreakingChangeType.DIRECTIVE_REMOVED,
                    f"{old_directive.name} was removed.",
                )
            )

    return schema_changes


def find_removed_directive_args(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    schema_changes: List[BreakingChange] = []

    new_directives = {directive.name: directive for directive in new_schema.directives}
    for old_directive in old_schema.directives:
        new_directive = new_directives.get(old_directive.name)
        if not new_directive:
            continue

        for old_arg_name in old_directive.args:
            if old_arg_name not in new_directive.args:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.DIRECTIVE_ARG_REMOVED,
                        f"{old_arg_name} was removed from {new_directive.name}.",
                    )
                )

    return schema_changes


def find_added_non_null_directive_args(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    schema_changes: List[BreakingChange] = []

    new_directives = {directive.name: directive for directive in new_schema.directives}
    for old_directive in old_schema.directives:
        new_directive = new_directives.get(old_directive.name)
        if not new_directive:
            continue

        for new_arg_name, new_arg in new_directive.args.items():
            old_arg = old_directive.args.get(new_arg_name)
            if not old_arg and is_required_argument(new_arg):
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.REQUIRED_DIRECTIVE_ARG_ADDED,
                        f"A required arg {new_arg_name} on directive"
                        f" {new_directive.name} was added.",
                    )
                )

    return schema_changes


def find_removed_directive_locations(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    schema_changes: List[BreakingChange] = []

    new_directives = {directive.name: directive for directive in new_schema.directives}
    for old_directive in old_schema.directives:
        new_directive = new_directives.get(old_directive.name)
        if not new_directive:
            continue

        for location in old_directive.locations:
            if location not in new_directive.locations:
                schema_changes.append(
                    BreakingChange(
                        BreakingChangeType.DIRECTIVE_LOCATION_REMOVED,
                        f"{location.name} was removed from {new_directive.name}.",
                    )
                )

    return schema_changes
