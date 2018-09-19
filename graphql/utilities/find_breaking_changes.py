from enum import Enum
from typing import Dict, List, NamedTuple, Union, cast

from ..error import INVALID
from ..language import DirectiveLocation
from ..type import (
    GraphQLArgument,
    GraphQLDirective,
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
    "find_removed_types",
    "find_types_that_changed_kind",
    "find_fields_that_changed_type_on_object_or_interface_types",
    "find_fields_that_changed_type_on_input_object_types",
    "find_types_removed_from_unions",
    "find_values_removed_from_enums",
    "find_arg_changes",
    "find_interfaces_removed_from_object_types",
    "find_removed_directives",
    "find_removed_directive_args",
    "find_added_non_null_directive_args",
    "find_removed_locations_for_directive",
    "find_removed_directive_locations",
    "find_values_added_to_enums",
    "find_interfaces_added_to_object_types",
    "find_types_added_to_unions",
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


class BreakingAndDangerousChanges(NamedTuple):
    breaking_changes: List[BreakingChange]
    dangerous_changes: List[DangerousChange]


def find_breaking_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find breaking changes.

    Given two schemas, returns a list containing descriptions of all the
    types of breaking changes covered by the other functions down below.
    """
    return (
        find_removed_types(old_schema, new_schema)
        + find_types_that_changed_kind(old_schema, new_schema)
        + find_fields_that_changed_type_on_object_or_interface_types(
            old_schema, new_schema
        )
        + find_fields_that_changed_type_on_input_object_types(
            old_schema, new_schema
        ).breaking_changes
        + find_types_removed_from_unions(old_schema, new_schema)
        + find_values_removed_from_enums(old_schema, new_schema)
        + find_arg_changes(old_schema, new_schema).breaking_changes
        + find_interfaces_removed_from_object_types(old_schema, new_schema)
        + find_removed_directives(old_schema, new_schema)
        + find_removed_directive_args(old_schema, new_schema)
        + find_added_non_null_directive_args(old_schema, new_schema)
        + find_removed_directive_locations(old_schema, new_schema)
    )


def find_dangerous_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    """Find dangerous changes.

    Given two schemas, returns a list containing descriptions of all the types
    of potentially dangerous changes covered by the other functions down below.
    """
    return (
        find_arg_changes(old_schema, new_schema).dangerous_changes
        + find_values_added_to_enums(old_schema, new_schema)
        + find_interfaces_added_to_object_types(old_schema, new_schema)
        + find_types_added_to_unions(old_schema, new_schema)
        + find_fields_that_changed_type_on_input_object_types(
            old_schema, new_schema
        ).dangerous_changes
    )


def find_removed_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find removed types.

    Given two schemas, returns a list containing descriptions of any breaking
    changes in the newSchema related to removing an entire type.
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    breaking_changes = []
    for type_name in old_type_map:
        if type_name not in new_type_map:
            breaking_changes.append(
                BreakingChange(
                    BreakingChangeType.TYPE_REMOVED, f"{type_name} was removed."
                )
            )
    return breaking_changes


def find_types_that_changed_kind(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find types that changed kind

    Given two schemas, returns a list containing descriptions of any breaking
    changes in the newSchema related to changing the type of a type.
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    breaking_changes = []
    for type_name in old_type_map:
        if type_name not in new_type_map:
            continue
        old_type = old_type_map[type_name]
        new_type = new_type_map[type_name]
        if old_type.__class__ is not new_type.__class__:
            breaking_changes.append(
                BreakingChange(
                    BreakingChangeType.TYPE_CHANGED_KIND,
                    f"{type_name} changed from {type_kind_name(old_type)}"
                    f" to {type_kind_name(new_type)}.",
                )
            )
    return breaking_changes


def find_arg_changes(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> BreakingAndDangerousChanges:
    """Find argument changes.

    Given two schemas, returns a list containing descriptions of any
    breaking or dangerous changes in the new_schema related to arguments
    (such as removal or change of type of an argument, or a change in an
    argument's default value).
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    breaking_changes: List[BreakingChange] = []
    dangerous_changes: List[DangerousChange] = []

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

        old_type_fields = old_type.fields
        new_type_fields = new_type.fields
        for field_name in old_type_fields:
            if field_name not in new_type_fields:
                continue

            old_args = old_type_fields[field_name].args
            new_args = new_type_fields[field_name].args
            for arg_name, old_arg in old_args.items():
                new_arg = new_args.get(arg_name)
                if not new_arg:
                    # Arg not present
                    breaking_changes.append(
                        BreakingChange(
                            BreakingChangeType.ARG_REMOVED,
                            f"{old_type.name}.{field_name} arg"
                            f" {arg_name} was removed",
                        )
                    )
                    continue
                is_safe = is_change_safe_for_input_object_field_or_field_arg(
                    old_arg.type, new_arg.type
                )
                if not is_safe:
                    breaking_changes.append(
                        BreakingChange(
                            BreakingChangeType.ARG_CHANGED_KIND,
                            f"{old_type.name}.{field_name} arg"
                            f" {arg_name} has changed type from"
                            f" {old_arg.type} to {new_arg.type}",
                        )
                    )
                elif (
                    old_arg.default_value is not INVALID
                    and old_arg.default_value != new_arg.default_value
                ):
                    dangerous_changes.append(
                        DangerousChange(
                            DangerousChangeType.ARG_DEFAULT_VALUE_CHANGE,
                            f"{old_type.name}.{field_name} arg"
                            f" {arg_name} has changed defaultValue",
                        )
                    )

            # Check if arg was added to the field
            for arg_name in new_args:
                if arg_name not in old_args:
                    new_arg_def = new_args[arg_name]
                    if is_required_argument(new_arg_def):
                        breaking_changes.append(
                            BreakingChange(
                                BreakingChangeType.REQUIRED_ARG_ADDED,
                                f"A required arg {arg_name} on"
                                f" {type_name}.{field_name} was added",
                            )
                        )
                    else:
                        dangerous_changes.append(
                            DangerousChange(
                                DangerousChangeType.OPTIONAL_ARG_ADDED,
                                f"An optional arg {arg_name} on"
                                f" {type_name}.{field_name} was added",
                            )
                        )

    return BreakingAndDangerousChanges(breaking_changes, dangerous_changes)


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
    raise TypeError(f"Unknown type {type_.__class__.__name__}")


def find_fields_that_changed_type_on_object_or_interface_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    breaking_changes = []
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

        old_type_fields_def = old_type.fields
        new_type_fields_def = new_type.fields
        for field_name in old_type_fields_def:
            # Check if the field is missing on the type in the new schema.
            if field_name not in new_type_fields_def:
                breaking_changes.append(
                    BreakingChange(
                        BreakingChangeType.FIELD_REMOVED,
                        f"{type_name}.{field_name} was removed.",
                    )
                )
            else:
                old_field_type = old_type_fields_def[field_name].type
                new_field_type = new_type_fields_def[field_name].type
                is_safe = is_change_safe_for_object_or_interface_field(
                    old_field_type, new_field_type
                )
                if not is_safe:
                    old_field_type_string = (
                        old_field_type.name
                        if is_named_type(old_field_type)
                        else str(old_field_type)
                    )
                    new_field_type_string = (
                        new_field_type.name
                        if is_named_type(new_field_type)
                        else str(new_field_type)
                    )
                    breaking_changes.append(
                        BreakingChange(
                            BreakingChangeType.FIELD_CHANGED_KIND,
                            f"{type_name}.{field_name} changed type"
                            f" from {old_field_type_string}"
                            f" to {new_field_type_string}.",
                        )
                    )

    return breaking_changes


def find_fields_that_changed_type_on_input_object_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> BreakingAndDangerousChanges:
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    breaking_changes = []
    dangerous_changes = []
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_input_object_type(old_type) and is_input_object_type(new_type)):
            continue
        old_type = cast(GraphQLInputObjectType, old_type)
        new_type = cast(GraphQLInputObjectType, new_type)

        old_type_fields_def = old_type.fields
        new_type_fields_def = new_type.fields
        for field_name in old_type_fields_def:
            # Check if the field is missing on the type in the new schema.
            if field_name not in new_type_fields_def:
                breaking_changes.append(
                    BreakingChange(
                        BreakingChangeType.FIELD_REMOVED,
                        f"{type_name}.{field_name} was removed.",
                    )
                )
            else:
                old_field_type = old_type_fields_def[field_name].type
                new_field_type = new_type_fields_def[field_name].type

                is_safe = is_change_safe_for_input_object_field_or_field_arg(
                    old_field_type, new_field_type
                )
                if not is_safe:
                    old_field_type_string = (
                        cast(GraphQLNamedType, old_field_type).name
                        if is_named_type(old_field_type)
                        else str(old_field_type)
                    )
                    new_field_type_string = (
                        cast(GraphQLNamedType, new_field_type).name
                        if is_named_type(new_field_type)
                        else str(new_field_type)
                    )
                    breaking_changes.append(
                        BreakingChange(
                            BreakingChangeType.FIELD_CHANGED_KIND,
                            f"{type_name}.{field_name} changed type"
                            f" from {old_field_type_string}"
                            f" to {new_field_type_string}.",
                        )
                    )

        # Check if a field was added to the input object type
        for field_name in new_type_fields_def:
            if field_name not in old_type_fields_def:
                if is_required_input_field(new_type_fields_def[field_name]):
                    breaking_changes.append(
                        BreakingChange(
                            BreakingChangeType.REQUIRED_INPUT_FIELD_ADDED,
                            f"A required field {field_name} on"
                            f" input type {type_name} was added.",
                        )
                    )
                else:
                    dangerous_changes.append(
                        DangerousChange(
                            DangerousChangeType.OPTIONAL_INPUT_FIELD_ADDED,
                            f"An optional field {field_name} on"
                            f" input type {type_name} was added.",
                        )
                    )

    return BreakingAndDangerousChanges(breaking_changes, dangerous_changes)


def is_change_safe_for_object_or_interface_field(
    old_type: GraphQLType, new_type: GraphQLType
) -> bool:
    if is_named_type(old_type):
        return (
            # if they're both named types, see if their names are equivalent
            (
                is_named_type(new_type)
                and cast(GraphQLNamedType, old_type).name
                == cast(GraphQLNamedType, new_type).name
            )
            or
            # moving from nullable to non-null of same underlying type is safe
            (
                is_non_null_type(new_type)
                and is_change_safe_for_object_or_interface_field(
                    old_type, cast(GraphQLNonNull, new_type).of_type
                )
            )
        )
    elif is_list_type(old_type):
        return (
            # if they're both lists, make sure underlying types are compatible
            (
                is_list_type(new_type)
                and is_change_safe_for_object_or_interface_field(
                    cast(GraphQLList, old_type).of_type,
                    cast(GraphQLList, new_type).of_type,
                )
            )
            or
            # moving from nullable to non-null of same underlying type is safe
            (
                is_non_null_type(new_type)
                and is_change_safe_for_object_or_interface_field(
                    old_type, cast(GraphQLNonNull, new_type).of_type
                )
            )
        )
    elif is_non_null_type(old_type):
        # if they're both non-null, make sure underlying types are compatible
        return is_non_null_type(
            new_type
        ) and is_change_safe_for_object_or_interface_field(
            cast(GraphQLNonNull, old_type).of_type,
            cast(GraphQLNonNull, new_type).of_type,
        )
    else:
        return False


def is_change_safe_for_input_object_field_or_field_arg(
    old_type: GraphQLType, new_type: GraphQLType
) -> bool:
    if is_named_type(old_type):
        # if they're both named types, see if their names are equivalent
        return (
            is_named_type(new_type)
            and cast(GraphQLNamedType, old_type).name
            == cast(GraphQLNamedType, new_type).name
        )
    elif is_list_type(old_type):
        # if they're both lists, make sure underlying types are compatible
        return is_list_type(
            new_type
        ) and is_change_safe_for_input_object_field_or_field_arg(
            cast(GraphQLList, old_type).of_type, cast(GraphQLList, new_type).of_type
        )
    elif is_non_null_type(old_type):
        return (
            # if they're both non-null,
            # make sure the underlying types are compatible
            (
                is_non_null_type(new_type)
                and is_change_safe_for_input_object_field_or_field_arg(
                    cast(GraphQLNonNull, old_type).of_type,
                    cast(GraphQLNonNull, new_type).of_type,
                )
            )
            or
            # moving from non-null to nullable of same underlying type is safe
            (
                not is_non_null_type(new_type)
                and is_change_safe_for_input_object_field_or_field_arg(
                    cast(GraphQLNonNull, old_type).of_type, new_type
                )
            )
        )
    else:
        return False


def find_types_removed_from_unions(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find types removed from unions.

    Given two schemas, returns a list containing descriptions of any breaking
    changes in the new_schema related to removing types from a union type.
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    types_removed_from_union = []
    for old_type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(old_type_name)
        if not (is_union_type(old_type) and is_union_type(new_type)):
            continue
        old_type = cast(GraphQLUnionType, old_type)
        new_type = cast(GraphQLUnionType, new_type)
        type_names_in_new_union = {type_.name for type_ in new_type.types}
        for type_ in old_type.types:
            type_name = type_.name
            if type_name not in type_names_in_new_union:
                types_removed_from_union.append(
                    BreakingChange(
                        BreakingChangeType.TYPE_REMOVED_FROM_UNION,
                        f"{type_name} was removed" f" from union type {old_type_name}.",
                    )
                )
    return types_removed_from_union


def find_types_added_to_unions(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    """Find types added to union.

    Given two schemas, returns a list containing descriptions of any dangerous
    changes in the new_schema related to adding types to a union type.
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    types_added_to_union = []
    for new_type_name, new_type in new_type_map.items():
        old_type = old_type_map.get(new_type_name)
        if not (is_union_type(old_type) and is_union_type(new_type)):
            continue
        old_type = cast(GraphQLUnionType, old_type)
        new_type = cast(GraphQLUnionType, new_type)
        type_names_in_old_union = {type_.name for type_ in old_type.types}
        for type_ in new_type.types:
            type_name = type_.name
            if type_name not in type_names_in_old_union:
                types_added_to_union.append(
                    DangerousChange(
                        DangerousChangeType.TYPE_ADDED_TO_UNION,
                        f"{type_name} was added to union type {new_type_name}.",
                    )
                )
    return types_added_to_union


def find_values_removed_from_enums(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    """Find values removed from enums.

    Given two schemas, returns a list containing descriptions of any breaking
    changes in the new_schema related to removing values from an enum type.
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    values_removed_from_enums = []
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_enum_type(old_type) and is_enum_type(new_type)):
            continue
        old_type = cast(GraphQLEnumType, old_type)
        new_type = cast(GraphQLEnumType, new_type)
        values_in_new_enum = new_type.values
        for value_name in old_type.values:
            if value_name not in values_in_new_enum:
                values_removed_from_enums.append(
                    BreakingChange(
                        BreakingChangeType.VALUE_REMOVED_FROM_ENUM,
                        f"{value_name} was removed from enum type {type_name}.",
                    )
                )
    return values_removed_from_enums


def find_values_added_to_enums(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    """Find values added to enums.

    Given two schemas, returns a list containing descriptions of any dangerous
    changes in the new_schema related to adding values to an enum type.
    """
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map

    values_added_to_enums = []
    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_enum_type(old_type) and is_enum_type(new_type)):
            continue
        old_type = cast(GraphQLEnumType, old_type)
        new_type = cast(GraphQLEnumType, new_type)
        values_in_old_enum = old_type.values
        for value_name in new_type.values:
            if value_name not in values_in_old_enum:
                values_added_to_enums.append(
                    DangerousChange(
                        DangerousChangeType.VALUE_ADDED_TO_ENUM,
                        f"{value_name} was added to enum type {type_name}.",
                    )
                )
    return values_added_to_enums


def find_interfaces_removed_from_object_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    breaking_changes = []

    for type_name, old_type in old_type_map.items():
        new_type = new_type_map.get(type_name)
        if not (is_object_type(old_type) and is_object_type(new_type)):
            continue
        old_type = cast(GraphQLObjectType, old_type)
        new_type = cast(GraphQLObjectType, new_type)

        old_interfaces = old_type.interfaces
        new_interfaces = new_type.interfaces
        for old_interface in old_interfaces:
            if not any(
                interface.name == old_interface.name for interface in new_interfaces
            ):
                breaking_changes.append(
                    BreakingChange(
                        BreakingChangeType.INTERFACE_REMOVED_FROM_OBJECT,
                        f"{type_name} no longer implements interface"
                        f" {old_interface.name}.",
                    )
                )

    return breaking_changes


def find_interfaces_added_to_object_types(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[DangerousChange]:
    old_type_map = old_schema.type_map
    new_type_map = new_schema.type_map
    interfaces_added_to_object_types = []

    for type_name, new_type in new_type_map.items():
        old_type = old_type_map.get(type_name)
        if not (is_object_type(old_type) and is_object_type(new_type)):
            continue
        old_type = cast(GraphQLObjectType, old_type)
        new_type = cast(GraphQLObjectType, new_type)

        old_interfaces = old_type.interfaces
        new_interfaces = new_type.interfaces
        for new_interface in new_interfaces:
            if not any(
                interface.name == new_interface.name for interface in old_interfaces
            ):
                interfaces_added_to_object_types.append(
                    DangerousChange(
                        DangerousChangeType.INTERFACE_ADDED_TO_OBJECT,
                        f"{new_interface.name} added to interfaces implemented"
                        f" by {type_name}.",
                    )
                )

    return interfaces_added_to_object_types


def find_removed_directives(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    removed_directives = []

    new_schema_directive_map = get_directive_map_for_schema(new_schema)
    for directive in old_schema.directives:
        if directive.name not in new_schema_directive_map:
            removed_directives.append(
                BreakingChange(
                    BreakingChangeType.DIRECTIVE_REMOVED,
                    f"{directive.name} was removed",
                )
            )

    return removed_directives


def find_removed_args_for_directive(
    old_directive: GraphQLDirective, new_directive: GraphQLDirective
) -> List[str]:
    new_arg_map = new_directive.args
    return [arg_name for arg_name in old_directive.args if arg_name not in new_arg_map]


def find_removed_directive_args(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    removed_directive_args = []
    old_schema_directive_map = get_directive_map_for_schema(old_schema)

    for new_directive in new_schema.directives:
        old_directive = old_schema_directive_map.get(new_directive.name)
        if not old_directive:
            continue

        for arg_name in find_removed_args_for_directive(old_directive, new_directive):
            removed_directive_args.append(
                BreakingChange(
                    BreakingChangeType.DIRECTIVE_ARG_REMOVED,
                    f"{arg_name} was removed from {new_directive.name}",
                )
            )

    return removed_directive_args


def find_added_args_for_directive(
    old_directive: GraphQLDirective, new_directive: GraphQLDirective
) -> Dict[str, GraphQLArgument]:
    old_arg_map = old_directive.args
    return {
        arg_name: arg
        for arg_name, arg in new_directive.args.items()
        if arg_name not in old_arg_map
    }


def find_added_non_null_directive_args(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    added_non_nullable_args = []
    old_schema_directive_map = get_directive_map_for_schema(old_schema)

    for new_directive in new_schema.directives:
        old_directive = old_schema_directive_map.get(new_directive.name)
        if not old_directive:
            continue

        for arg_name, arg in find_added_args_for_directive(
            old_directive, new_directive
        ).items():
            if is_required_argument(arg):
                added_non_nullable_args.append(
                    BreakingChange(
                        BreakingChangeType.REQUIRED_DIRECTIVE_ARG_ADDED,
                        f"A required arg {arg_name} on directive"
                        f" {new_directive.name} was added",
                    )
                )

    return added_non_nullable_args


def find_removed_locations_for_directive(
    old_directive: GraphQLDirective, new_directive: GraphQLDirective
) -> List[DirectiveLocation]:
    new_location_set = set(new_directive.locations)
    return [
        old_location
        for old_location in old_directive.locations
        if old_location not in new_location_set
    ]


def find_removed_directive_locations(
    old_schema: GraphQLSchema, new_schema: GraphQLSchema
) -> List[BreakingChange]:
    removed_locations = []
    old_schema_directive_map = get_directive_map_for_schema(old_schema)

    for new_directive in new_schema.directives:
        old_directive = old_schema_directive_map.get(new_directive.name)
        if not old_directive:
            continue

        for location in find_removed_locations_for_directive(
            old_directive, new_directive
        ):
            removed_locations.append(
                BreakingChange(
                    BreakingChangeType.DIRECTIVE_LOCATION_REMOVED,
                    f"{location.name} was removed from {new_directive.name}",
                )
            )

    return removed_locations


def get_directive_map_for_schema(schema: GraphQLSchema) -> Dict[str, GraphQLDirective]:
    return {directive.name: directive for directive in schema.directives}
