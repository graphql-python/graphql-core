from typing import Any, Dict, List, NamedTuple, Optional, Union, cast

from ..error import GraphQLError, INVALID
from ..language import (
    ArgumentNode,
    DirectiveNode,
    ExecutableDefinitionNode,
    FieldNode,
    NullValueNode,
    SchemaDefinitionNode,
    SelectionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    VariableDefinitionNode,
    VariableNode,
    print_ast,
)
from ..pyutils import inspect
from ..type import (
    GraphQLDirective,
    GraphQLField,
    GraphQLInputType,
    GraphQLSchema,
    is_input_type,
    is_non_null_type,
)
from ..utilities import coerce_value, type_from_ast, value_from_ast

__all__ = ["get_variable_values", "get_argument_values", "get_directive_values"]


class CoercedVariableValues(NamedTuple):
    errors: Optional[List[GraphQLError]]
    coerced: Optional[Dict[str, Any]]


def get_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: List[VariableDefinitionNode],
    inputs: Dict[str, Any],
) -> CoercedVariableValues:
    """Get coerced variable values based on provided definitions.

    Prepares a dict of variable values of the correct type based on the provided
    variable definitions and arbitrary input. If the input cannot be parsed to match
    the variable definitions, a GraphQLError will be thrown.
    """
    errors: List[GraphQLError] = []
    coerced_values: Dict[str, Any] = {}
    for var_def_node in var_def_nodes:
        var_name = var_def_node.variable.name.value
        var_type = type_from_ast(schema, var_def_node.type)
        if not is_input_type(var_type):
            # Must use input types for variables. This should be caught during
            # validation, however is checked again here for safety.
            errors.append(
                GraphQLError(
                    f"Variable '${var_name}' expected value of type"
                    f" '{print_ast(var_def_node.type)}'"
                    " which cannot be used as an input type.",
                    var_def_node.type,
                )
            )
        else:
            var_type = cast(GraphQLInputType, var_type)
            has_value = var_name in inputs
            value = inputs[var_name] if has_value else INVALID
            if not has_value and var_def_node.default_value:
                # If no value was provided to a variable with a default value, use the
                # default value.
                coerced_values[var_name] = value_from_ast(
                    var_def_node.default_value, var_type
                )
            elif (not has_value or value is None) and is_non_null_type(var_type):
                errors.append(
                    GraphQLError(
                        f"Variable '${var_name}' of non-null type"
                        f" '{var_type}' must not be null."
                        if has_value
                        else f"Variable '${var_name}' of required type"
                        f" '{var_type}' was not provided.",
                        var_def_node,
                    )
                )
            elif has_value:
                if value is None:
                    # If the explicit value `None` was provided, an entry in the
                    # coerced values must exist as the value `None`.
                    coerced_values[var_name] = None
                else:
                    # Otherwise, a non-null value was provided, coerce it to the
                    # expected type or report an error if coercion fails.
                    coerced = coerce_value(value, var_type, var_def_node)
                    coercion_errors = coerced.errors
                    if coercion_errors:
                        for error in coercion_errors:
                            error.message = (
                                f"Variable '${var_name}' got invalid"
                                f" value {inspect(value)}; {error.message}"
                            )
                        errors.extend(coercion_errors)
                    else:
                        coerced_values[var_name] = coerced.value
    return (
        CoercedVariableValues(errors, None)
        if errors
        else CoercedVariableValues(None, coerced_values)
    )


def get_argument_values(
    type_def: Union[GraphQLField, GraphQLDirective],
    node: Union[FieldNode, DirectiveNode],
    variable_values: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Get coerced argument values based on provided definitions and nodes.

    Prepares an dict of argument values given a list of argument definitions and list
    of argument AST nodes.
    """
    coerced_values: Dict[str, Any] = {}
    arg_defs = type_def.args
    arg_nodes = node.arguments
    if not arg_defs or arg_nodes is None:
        return coerced_values
    arg_node_map = {arg.name.value: arg for arg in arg_nodes}
    for name, arg_def in arg_defs.items():
        arg_type = arg_def.type
        argument_node = cast(ArgumentNode, arg_node_map.get(name))
        variable_values = cast(Dict[str, Any], variable_values)
        if argument_node and isinstance(argument_node.value, VariableNode):
            variable_name = argument_node.value.name.value
            has_value = variable_values and variable_name in variable_values
            is_null = has_value and variable_values[variable_name] is None
        else:
            has_value = argument_node is not None
            is_null = has_value and isinstance(argument_node.value, NullValueNode)
        if not has_value and arg_def.default_value is not INVALID:
            # If no argument was provided where the definition has a default value,
            # use the default value.
            # If an out name exists, we use that as the name (extension of GraphQL.js).
            coerced_values[arg_def.out_name or name] = arg_def.default_value
        elif (not has_value or is_null) and is_non_null_type(arg_type):
            # If no argument or a null value was provided to an argument with a non-null
            # type (required), produce a field error.
            if is_null:
                raise GraphQLError(
                    f"Argument '{name}' of non-null type"
                    f" '{arg_type}' must not be null.",
                    argument_node.value,
                )
            elif argument_node and isinstance(argument_node.value, VariableNode):
                raise GraphQLError(
                    f"Argument '{name}' of required type"
                    f" '{arg_type}' was provided the variable"
                    f" '${variable_name}'"
                    " which was not provided a runtime value.",
                    argument_node.value,
                )
            else:
                raise GraphQLError(
                    f"Argument '{name}' of required type '{arg_type}'"
                    " was not provided.",
                    node,
                )
        elif has_value:
            if isinstance(argument_node.value, NullValueNode):
                # If the explicit value `None` was provided, an entry in the coerced
                # values must exist as the value `None`.
                coerced_values[arg_def.out_name or name] = None
            elif isinstance(argument_node.value, VariableNode):
                variable_name = argument_node.value.name.value
                # Note: This Does no further checking that this variable is correct.
                # This assumes that this query has been validated and the variable
                # usage here is of the correct type.
                coerced_values[arg_def.out_name or name] = variable_values[
                    variable_name
                ]
            else:
                value_node = argument_node.value
                coerced_value = value_from_ast(value_node, arg_type, variable_values)
                if coerced_value is INVALID:
                    # Note: `values_of_correct_type` validation should catch this before
                    # execution. This is a runtime check to ensure execution does not
                    # continue with an invalid argument value.
                    raise GraphQLError(
                        f"Argument '{name}'"
                        f" has invalid value {print_ast(value_node)}.",
                        argument_node.value,
                    )
                coerced_values[arg_def.out_name or name] = coerced_value
    return coerced_values


NodeWithDirective = Union[
    ExecutableDefinitionNode,
    SelectionNode,
    SchemaDefinitionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
]


def get_directive_values(
    directive_def: GraphQLDirective,
    node: NodeWithDirective,
    variable_values: Dict[str, Any] = None,
) -> Optional[Dict[str, Any]]:
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
