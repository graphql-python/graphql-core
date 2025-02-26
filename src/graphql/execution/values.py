"""Helpers for handling values"""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, List, Union

from ..error import GraphQLError
from ..language import (
    DirectiveNode,
    EnumValueDefinitionNode,
    ExecutableDefinitionNode,
    FieldDefinitionNode,
    FieldNode,
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
    is_input_type,
    is_non_null_type,
)
from ..utilities.coerce_input_value import coerce_input_value
from ..utilities.type_from_ast import type_from_ast
from ..utilities.value_from_ast import value_from_ast

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

__all__ = ["get_argument_values", "get_directive_values", "get_variable_values"]

CoercedVariableValues: TypeAlias = Union[List[GraphQLError], Dict[str, Any]]


def get_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: Collection[VariableDefinitionNode],
    inputs: dict[str, Any],
    max_errors: int | None = None,
) -> CoercedVariableValues:
    """Get coerced variable values based on provided definitions.

    Prepares a dict of variable values of the correct type based on the provided
    variable definitions and arbitrary input. If the input cannot be parsed to match
    the variable definitions, a GraphQLError will be raised.
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
        coerced = coerce_variable_values(schema, var_def_nodes, inputs, on_error)
        if not errors:
            return coerced
    except GraphQLError as e:
        errors.append(e)

    return errors


def coerce_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: Collection[VariableDefinitionNode],
    inputs: dict[str, Any],
    on_error: Callable[[GraphQLError], None],
) -> dict[str, Any]:
    coerced_values: dict[str, Any] = {}
    for var_def_node in var_def_nodes:
        var_name = var_def_node.variable.name.value
        var_type = type_from_ast(schema, var_def_node.type)
        if not is_input_type(var_type):
            # Must use input types for variables. This should be caught during
            # validation, however is checked again here for safety.
            var_type_str = print_ast(var_def_node.type)
            on_error(
                GraphQLError(
                    f"Variable '${var_name}' expected value of type '{var_type_str}'"
                    " which cannot be used as an input type.",
                    var_def_node.type,
                )
            )
            continue

        if var_name not in inputs:
            if var_def_node.default_value:
                coerced_values[var_name] = value_from_ast(
                    var_def_node.default_value, var_type
                )
            elif is_non_null_type(var_type):  # pragma: no cover else
                var_type_str = inspect(var_type)
                on_error(
                    GraphQLError(
                        f"Variable '${var_name}' of required type '{var_type_str}'"
                        " was not provided.",
                        var_def_node,
                    )
                )
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

        coerced_values[var_name] = coerce_input_value(
            value, var_type, on_input_value_error
        )

    return coerced_values


def get_argument_values(
    type_def: GraphQLField | GraphQLDirective,
    node: FieldNode | DirectiveNode,
    variable_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get coerced argument values based on provided definitions and nodes.

    Prepares a dict of argument values given a list of argument definitions and list
    of argument AST nodes.
    """
    coerced_values: dict[str, Any] = {}
    arg_node_map = {arg.name.value: arg for arg in node.arguments or []}

    for name, arg_def in type_def.args.items():
        arg_type = arg_def.type
        argument_node = arg_node_map.get(name)

        if argument_node is None:
            value = arg_def.default_value
            if value is not Undefined:
                if is_input_object_type(arg_def.type):
                    # coerce input value so that out_names are used
                    value = coerce_input_value(value, arg_def.type)
                coerced_values[arg_def.out_name or name] = value
            elif is_non_null_type(arg_type):  # pragma: no cover else
                msg = (
                    f"Argument '{name}' of required type '{arg_type}' was not provided."
                )
                raise GraphQLError(msg, node)
            continue  # pragma: no cover

        value_node = argument_node.value
        is_null = isinstance(argument_node.value, NullValueNode)

        if isinstance(value_node, VariableNode):
            variable_name = value_node.name.value
            if variable_values is None or variable_name not in variable_values:
                value = arg_def.default_value
                if value is not Undefined:
                    if is_input_object_type(arg_def.type):
                        # coerce input value so that out_names are used
                        value = coerce_input_value(value, arg_def.type)
                    coerced_values[arg_def.out_name or name] = value
                elif is_non_null_type(arg_type):  # pragma: no cover else
                    msg = (
                        f"Argument '{name}' of required type '{arg_type}'"
                        f" was provided the variable '${variable_name}'"
                        " which was not provided a runtime value."
                    )
                    raise GraphQLError(msg, value_node)
                continue  # pragma: no cover
            variable_value = variable_values[variable_name]
            is_null = variable_value is None or variable_value is Undefined

        if is_null and is_non_null_type(arg_type):
            msg = f"Argument '{name}' of non-null type '{arg_type}' must not be null."
            raise GraphQLError(msg, value_node)

        coerced_value = value_from_ast(value_node, arg_type, variable_values)
        if coerced_value is Undefined:
            # Note: `values_of_correct_type` validation should catch this before
            # execution. This is a runtime check to ensure execution does not
            # continue with an invalid argument value.
            msg = f"Argument '{name}' has invalid value {print_ast(value_node)}."
            raise GraphQLError(msg, value_node)
        coerced_values[arg_def.out_name or name] = coerced_value

    return coerced_values


NodeWithDirective: TypeAlias = Union[
    EnumValueDefinitionNode,
    ExecutableDefinitionNode,
    FieldDefinitionNode,
    InputValueDefinitionNode,
    SelectionNode,
    SchemaDefinitionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
]


def get_directive_values(
    directive_def: GraphQLDirective,
    node: NodeWithDirective,
    variable_values: dict[str, Any] | None = None,
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
                return get_argument_values(directive_def, directive, variable_values)
    return None
