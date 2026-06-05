"""Helpers for handling values"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple, TypeAlias

from ..error import GraphQLError
from ..language import (
    DirectiveNode,
    EnumValueDefinitionNode,
    ExecutableDefinitionNode,
    FieldDefinitionNode,
    FieldNode,
    FragmentSpreadNode,
    InputValueDefinitionNode,
    NullValueNode,
    SchemaDefinitionNode,
    SelectionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    VariableDefinitionNode,
    VariableNode,
    print_ast,
)
from ..pyutils import Undefined, inspect, print_path_list
from ..type import (
    GraphQLDirective,
    GraphQLField,
    GraphQLSchema,
    is_input_object_type,
    is_non_null_type,
)
from ..utilities.coerce_input_value import (
    coerce_default_value,
    coerce_input_literal,
    coerce_input_value,
)
from .get_variable_signature import GraphQLVariableSignature, get_variable_signature

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from ..type import GraphQLArgument

__all__ = [
    "VariableValueSource",
    "VariableValues",
    "experimental_get_argument_values",
    "get_argument_values",
    "get_directive_values",
    "get_fragment_variable_values",
    "get_variable_values",
]


class VariableValueSource(NamedTuple):
    """The signature of a variable and its original input value."""

    signature: GraphQLVariableSignature
    value: Any = Undefined


class VariableValues(NamedTuple):
    """The coerced values of the variables and their original sources."""

    sources: dict[str, VariableValueSource]
    coerced: dict[str, Any]


VariableValuesOrErrors: TypeAlias = list[GraphQLError] | VariableValues


def get_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: Collection[VariableDefinitionNode],
    inputs: dict[str, Any],
    max_errors: int | None = None,
    hide_suggestions: bool = False,
) -> VariableValuesOrErrors:
    """Get coerced variable values based on provided definitions.

    Prepares an object map of variable values of the correct type based on the
    provided variable definitions and arbitrary input. If the input cannot be parsed
    to match the variable definitions, a GraphQLError will be raised.
    """
    errors: list[GraphQLError] = []

    def on_error(error: GraphQLError) -> None:
        if max_errors is not None and len(errors) >= max_errors:
            msg = (
                "Too many errors processing variables,"
                " error limit reached. Execution aborted."
            )
            raise GraphQLError(msg)
        errors.append(error)

    try:
        variable_values = coerce_variable_values(
            schema, var_def_nodes, inputs, on_error, hide_suggestions
        )
        if not errors:
            return variable_values
    except GraphQLError as e:
        errors.append(e)

    return errors


def coerce_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: Collection[VariableDefinitionNode],
    inputs: dict[str, Any],
    on_error: Callable[[GraphQLError], None],
    hide_suggestions: bool = False,
) -> VariableValues:
    sources: dict[str, VariableValueSource] = {}
    coerced: dict[str, Any] = {}
    for var_def_node in var_def_nodes:
        var_signature = get_variable_signature(schema, var_def_node)
        if isinstance(var_signature, GraphQLError):
            on_error(var_signature)
            continue

        var_name = var_signature.name
        var_type = var_signature.type
        if var_name not in inputs:
            default_value = var_signature.default_value
            if default_value:
                sources[var_name] = VariableValueSource(var_signature)
                coerced[var_name] = coerce_default_value(
                    default_value, var_type, hide_suggestions
                )
            elif is_non_null_type(var_type):
                var_type_str = inspect(var_type)
                on_error(
                    GraphQLError(
                        f"Variable '${var_name}' of required type '{var_type_str}'"
                        " was not provided.",
                        var_def_node,
                    )
                )
            else:
                sources[var_name] = VariableValueSource(var_signature)
            continue

        value = inputs[var_name]
        if value is None and is_non_null_type(var_type):
            var_type_str = inspect(var_type)
            on_error(
                GraphQLError(
                    f"Variable '${var_name}' of non-null type '{var_type_str}'"
                    " must not be null.",
                    var_def_node,
                )
            )
            continue

        def on_input_value_error(
            path: list[str | int],
            invalid_value: Any,
            error: GraphQLError,
            var_name: str = var_name,
            var_def_node: VariableDefinitionNode = var_def_node,
        ) -> None:
            invalid_str = inspect(invalid_value)
            prefix = f"Variable '${var_name}' got invalid value {invalid_str}"
            if path:
                prefix += f" at '{var_name}{print_path_list(path)}'"
            on_error(
                GraphQLError(
                    prefix + "; " + error.message,
                    var_def_node,
                    original_error=error,
                )
            )

        sources[var_name] = VariableValueSource(var_signature, value)
        coerced[var_name] = coerce_input_value(
            value, var_type, on_input_value_error, hide_suggestions=hide_suggestions
        )

    return VariableValues(sources, coerced)


def get_fragment_variable_values(
    fragment_spread_node: FragmentSpreadNode,
    fragment_signatures: Mapping[str, GraphQLVariableSignature],
    variable_values: VariableValues,
    fragment_variable_values: VariableValues | None = None,
    hide_suggestions: bool = False,
) -> VariableValues:
    """Get coerced variable values for a fragment spread.

    Prepares the variable values for a fragment spread, preserving the original
    sources of the variable values alongside the coerced values.
    """
    sources: dict[str, VariableValueSource] = {}
    for var_name, var_signature in fragment_signatures.items():
        value = Undefined
        if fragment_variable_values and var_name in fragment_variable_values.sources:
            value = fragment_variable_values.sources[var_name].value
        if value is None or value is Undefined:  # pragma: no branch
            # The preserved source value is not used directly here, but is
            # carried so that it can be made available downstream.
            source = variable_values.sources.get(var_name)
            value = source.value if source else Undefined
        sources[var_name] = VariableValueSource(var_signature, value)

    coerced = experimental_get_argument_values(
        fragment_spread_node,
        fragment_signatures,
        variable_values,
        fragment_variable_values,
        hide_suggestions,
    )

    return VariableValues(sources, coerced)


def get_argument_values(
    type_def: GraphQLField | GraphQLDirective,
    node: FieldNode | DirectiveNode,
    variable_values: VariableValues | None = None,
    hide_suggestions: bool = False,
) -> dict[str, Any]:
    """Get coerced argument values based on provided definitions and nodes.

    Prepares a dict of argument values given a list of argument definitions and list
    of argument AST nodes.
    """
    return experimental_get_argument_values(
        node, type_def.args, variable_values, hide_suggestions=hide_suggestions
    )


def experimental_get_argument_values(
    node: FieldNode | DirectiveNode | FragmentSpreadNode,
    arg_defs: Mapping[str, GraphQLArgument | GraphQLVariableSignature],
    variable_values: VariableValues | None = None,
    fragment_variable_values: VariableValues | None = None,
    hide_suggestions: bool = False,
) -> dict[str, Any]:
    """Get coerced argument values based on provided definitions and nodes.

    Prepares a dict of argument values given a mapping of argument definitions
    (which may be ``GraphQLArgument`` objects or fragment variable signatures) and
    list of argument AST nodes.
    """
    coerced_values: dict[str, Any] = {}
    arg_node_map = {arg.name.value: arg for arg in node.arguments or []}

    for name, arg_def in arg_defs.items():
        arg_type = arg_def.type
        out_name = getattr(arg_def, "out_name", None) or name
        argument_node = arg_node_map.get(name)

        if argument_node is None:
            default_value = arg_def.default_value
            if default_value:
                value = coerce_default_value(
                    default_value, arg_def.type, hide_suggestions
                )
                if default_value.literal is None and is_input_object_type(arg_def.type):
                    # coerce input value so that out_names are used
                    value = coerce_input_value(
                        value, arg_def.type, hide_suggestions=hide_suggestions
                    )
                coerced_values[out_name] = value
            elif is_non_null_type(arg_type):  # pragma: no branch
                msg = (
                    f"Argument '{name}' of required type '{arg_type}' was not provided."
                )
                raise GraphQLError(msg, node)
            continue  # pragma: no cover

        value_node = argument_node.value
        is_null = isinstance(argument_node.value, NullValueNode)

        if isinstance(value_node, VariableNode):
            variable_name = value_node.name.value
            scoped_variable_values = (
                fragment_variable_values
                if fragment_variable_values
                and variable_name in fragment_variable_values.sources
                else variable_values
            )
            if (
                scoped_variable_values is None
                or variable_name not in scoped_variable_values.coerced
            ):
                default_value = arg_def.default_value
                if default_value:
                    value = coerce_default_value(
                        default_value, arg_def.type, hide_suggestions
                    )
                    if default_value.literal is None and is_input_object_type(
                        arg_def.type
                    ):
                        # coerce input value so that out_names are used
                        value = coerce_input_value(
                            value, arg_def.type, hide_suggestions=hide_suggestions
                        )
                    coerced_values[out_name] = value
                elif is_non_null_type(arg_type):  # pragma: no branch
                    msg = (
                        f"Argument '{name}' of required type '{arg_type}'"
                        f" was provided the variable '${variable_name}'"
                        " which was not provided a runtime value."
                    )
                    raise GraphQLError(msg, value_node)
                continue  # pragma: no cover
            variable_value = scoped_variable_values.coerced[variable_name]
            is_null = variable_value is None or variable_value is Undefined

        if is_null and is_non_null_type(arg_type):
            msg = f"Argument '{name}' of non-null type '{arg_type}' must not be null."
            raise GraphQLError(msg, value_node)

        coerced_value = coerce_input_literal(
            value_node,
            arg_type,
            variable_values,
            fragment_variable_values,
            hide_suggestions,
        )
        if coerced_value is Undefined:
            # Note: `values_of_correct_type` validation should catch this before
            # execution. This is a runtime check to ensure execution does not
            # continue with an invalid argument value.
            msg = (
                f"Argument '{name}' of type '{inspect(arg_type)}'"
                f" has invalid value {print_ast(value_node)}."
            )
            raise GraphQLError(msg, value_node)
        coerced_values[out_name] = coerced_value

    return coerced_values


NodeWithDirective: TypeAlias = (
    EnumValueDefinitionNode
    | ExecutableDefinitionNode
    | FieldDefinitionNode
    | InputValueDefinitionNode
    | SelectionNode
    | SchemaDefinitionNode
    | TypeDefinitionNode
    | TypeExtensionNode
)


def get_directive_values(
    directive_def: GraphQLDirective,
    node: NodeWithDirective,
    variable_values: VariableValues | None = None,
    fragment_variable_values: VariableValues | None = None,
    hide_suggestions: bool = False,
) -> dict[str, Any] | None:
    """Get coerced argument values based on provided nodes.

    Prepares a dict of argument values given a directive definition and an AST node
    which may contain directives. Optionally also accepts a dict of variable values.

    If the directive does not exist on the node, returns None.
    """
    directives = node.directives
    if directives:
        directive_name = directive_def.name
        for directive in directives:
            if directive.name.value == directive_name:
                return experimental_get_argument_values(
                    directive,
                    directive_def.args,
                    variable_values,
                    fragment_variable_values,
                    hide_suggestions,
                )
    return None
