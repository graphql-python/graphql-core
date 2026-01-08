"""Printing GraphQL Schemas in SDL format"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..language import StringValueNode, print_ast
from ..language.block_string import is_printable_as_block_string
from ..pyutils import inspect
from ..type import (
    DEFAULT_DEPRECATION_REASON,
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLUnionType,
    is_introspection_type,
    is_specified_directive,
)
from .ast_from_value import ast_from_value

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "print_directive",
    "print_introspection_schema",
    "print_schema",
    "print_type",
    "print_value",
]


def print_schema(schema: GraphQLSchema) -> str:
    """Print the given GraphQL schema in SDL format."""
    return print_filtered_schema(
        schema, lambda n: not is_specified_directive(n), is_defined_type
    )


def print_introspection_schema(schema: GraphQLSchema) -> str:
    """Print the built-in introspection schema in SDL format."""
    return print_filtered_schema(schema, is_specified_directive, is_introspection_type)


def is_defined_type(type_: GraphQLNamedType) -> bool:
    """Check if the given named GraphQL type is a defined type."""
    return type_.name not in GraphQLNamedType.reserved_types


def print_filtered_schema(
    schema: GraphQLSchema,
    directive_filter: Callable[[GraphQLDirective], bool],
    type_filter: Callable[[GraphQLNamedType], bool],
) -> str:
    """Print a GraphQL schema filtered by the specified directives and types."""
    directives = filter(directive_filter, schema.directives)
    types = filter(type_filter, schema.type_map.values())

    return "\n\n".join(
        (
            *filter(None, (print_schema_definition(schema),)),
            *map(print_directive, directives),
            *map(print_type, types),
        )
    )


def print_schema_definition(schema: GraphQLSchema) -> str | None:
    """Print GraphQL schema definitions."""
    query_type = schema.query_type
    mutation_type = schema.mutation_type
    subscription_type = schema.subscription_type

    # Special case: When a schema has no root operation types, no valid schema
    # definition can be printed.
    if not query_type and not mutation_type and not subscription_type:
        return None

    # Only print a schema definition if there is a description or if it should
    # not be omitted because of having default type names.
    if not (schema.description is None and has_default_root_operation_types(schema)):
        return (
            print_description(schema)
            + "schema {\n"
            + (f"  query: {query_type.name}\n" if query_type else "")
            + (f"  mutation: {mutation_type.name}\n" if mutation_type else "")
            + (
                f"  subscription: {subscription_type.name}\n"
                if subscription_type
                else ""
            )
            + "}"
        )

    return None


def has_default_root_operation_types(schema: GraphQLSchema) -> bool:
    """Check whether a schema uses the default root operation type names.

    GraphQL schema define root types for each type of operation. These types are the
    same as any other type and can be named in any manner, however there is a common
    naming convention::

        schema {
          query: Query
          mutation: Mutation
          subscription: Subscription
        }

    When using this naming convention, the schema description can be omitted so
    long as these names are only used for operation types.

    Note however that if any of these default names are used elsewhere in the
    schema but not as a root operation type, the schema definition must still
    be printed to avoid ambiguity.
    """
    return (
        schema.query_type is schema.get_type("Query")
        and schema.mutation_type is schema.get_type("Mutation")
        and schema.subscription_type is schema.get_type("Subscription")
    )


def print_type(type_: GraphQLNamedType) -> str:
    """Print a named GraphQL type."""
    match type_:
        case GraphQLScalarType():
            return print_scalar(type_)
        case GraphQLObjectType():
            return print_object(type_)
        case GraphQLInterfaceType():
            return print_interface(type_)
        case GraphQLUnionType():
            return print_union(type_)
        case GraphQLEnumType():
            return print_enum(type_)
        case GraphQLInputObjectType():
            return print_input_object(type_)
        case _:  # pragma: no cover
            # Not reachable. All possible types have been considered.
            msg = f"Unexpected type: {inspect(type_)}."
            raise TypeError(msg)


def print_scalar(type_: GraphQLScalarType) -> str:
    """Print a GraphQL scalar type."""
    return (
        print_description(type_)
        + f"scalar {type_.name}"
        + print_specified_by_url(type_)
    )


def print_implemented_interfaces(
    type_: GraphQLObjectType | GraphQLInterfaceType,
) -> str:
    """Print the interfaces implemented by a GraphQL object or interface type."""
    interfaces = type_.interfaces
    return " implements " + " & ".join(i.name for i in interfaces) if interfaces else ""


def print_object(type_: GraphQLObjectType) -> str:
    """Print a GraphQL object type."""
    return (
        print_description(type_)
        + f"type {type_.name}"
        + print_implemented_interfaces(type_)
        + print_fields(type_)
    )


def print_interface(type_: GraphQLInterfaceType) -> str:
    """Print a GraphQL interface type."""
    return (
        print_description(type_)
        + f"interface {type_.name}"
        + print_implemented_interfaces(type_)
        + print_fields(type_)
    )


def print_union(type_: GraphQLUnionType) -> str:
    """Print a GraphQL union type."""
    types = type_.types
    possible_types = " = " + " | ".join(t.name for t in types) if types else ""
    return print_description(type_) + f"union {type_.name}" + possible_types


def print_enum(type_: GraphQLEnumType) -> str:
    """Print a GraphQL enum type."""
    values = [
        print_description(value, "  ", not i)
        + f"  {name}"
        + print_deprecated(value.deprecation_reason)
        for i, (name, value) in enumerate(type_.values.items())
    ]
    return print_description(type_) + f"enum {type_.name}" + print_block(values)


def print_input_object(type_: GraphQLInputObjectType) -> str:
    """Print a GraphQL input object type."""
    fields = [
        print_description(field, "  ", not i) + "  " + print_input_value(name, field)
        for i, (name, field) in enumerate(type_.fields.items())
    ]
    return (
        print_description(type_)
        + f"input {type_.name}"
        + (" @oneOf" if type_.is_one_of else "")
        + print_block(fields)
    )


def print_fields(type_: GraphQLObjectType | GraphQLInterfaceType) -> str:
    """Print the fields of a GraphQL object or interface type."""
    fields = [
        print_description(field, "  ", not i)
        + f"  {name}"
        + print_args(field.args, "  ")
        + f": {field.type}"
        + print_deprecated(field.deprecation_reason)
        for i, (name, field) in enumerate(type_.fields.items())
    ]
    return print_block(fields)


def print_block(items: list[str]) -> str:
    """Print a block with the given items."""
    return " {\n" + "\n".join(items) + "\n}" if items else ""


def print_args(args: dict[str, GraphQLArgument], indentation: str = "") -> str:
    """Print the given GraphQL arguments."""
    if not args:
        return ""

    # If every arg does not have a description, print them on one line.
    if all(arg.description is None for arg in args.values()):
        return (
            "("
            + ", ".join(print_input_value(name, arg) for name, arg in args.items())
            + ")"
        )

    return (
        "(\n"
        + "\n".join(
            print_description(arg, f"  {indentation}", not i)
            + f"  {indentation}"
            + print_input_value(name, arg)
            for i, (name, arg) in enumerate(args.items())
        )
        + f"\n{indentation})"
    )


def print_input_value(name: str, arg: GraphQLArgument) -> str:
    """Print an input value."""
    default_ast = ast_from_value(arg.default_value, arg.type)
    arg_decl = f"{name}: {arg.type}"
    if default_ast:
        arg_decl += f" = {print_ast(default_ast)}"
    return arg_decl + print_deprecated(arg.deprecation_reason)


def print_directive(directive: GraphQLDirective) -> str:
    """Print a GraphQL directive."""
    return (
        print_description(directive)
        + f"directive @{directive.name}"
        + print_args(directive.args)
        + (" repeatable" if directive.is_repeatable else "")
        + " on "
        + " | ".join(location.name for location in directive.locations)
    )


def print_deprecated(reason: str | None) -> str:
    """Print a deprecation reason."""
    if reason is None:
        return ""
    if reason != DEFAULT_DEPRECATION_REASON:
        ast_value = print_ast(StringValueNode(value=reason))
        return f" @deprecated(reason: {ast_value})"
    return " @deprecated"


def print_specified_by_url(scalar: GraphQLScalarType) -> str:
    """Print a specification URL."""
    if scalar.specified_by_url is None:
        return ""
    ast_value = print_ast(StringValueNode(value=scalar.specified_by_url))
    return f" @specifiedBy(url: {ast_value})"


def print_description(
    def_: GraphQLArgument
    | GraphQLDirective
    | GraphQLEnumValue
    | GraphQLNamedType
    | GraphQLSchema,
    indentation: str = "",
    first_in_block: bool = True,
) -> str:
    """Print a description."""
    description = def_.description
    if description is None:
        return ""

    block_string = print_ast(
        StringValueNode(
            value=description, block=is_printable_as_block_string(description)
        )
    )

    prefix = "\n" + indentation if indentation and not first_in_block else indentation

    return prefix + block_string.replace("\n", "\n" + indentation) + "\n"


def print_value(value: Any, type_: GraphQLInputType) -> str:
    """@deprecated: Convenience function for printing a Python value"""
    return print_ast(ast_from_value(value, type_))  # type: ignore
