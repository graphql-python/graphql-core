"""Helpers for handling fragment variable signatures"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from ..error import GraphQLError
from ..language import print_ast
from ..type import is_input_type
from ..utilities.type_from_ast import type_from_ast
from ..utilities.value_from_ast import value_from_ast

if TYPE_CHECKING:
    from ..language import VariableDefinitionNode
    from ..type import GraphQLInputType, GraphQLSchema

__all__ = ["GraphQLVariableSignature", "get_variable_signature"]


class GraphQLVariableSignature(NamedTuple):
    """A GraphQL variable signature is required to coerce a variable value.

    Designed to have a comparable interface to ``GraphQLArgument`` so that
    ``get_argument_values()`` can be reused for fragment arguments.
    """

    name: str
    type: GraphQLInputType
    default_value: Any


def get_variable_signature(
    schema: GraphQLSchema, var_def_node: VariableDefinitionNode
) -> GraphQLVariableSignature | GraphQLError:
    """Get a variable signature from a variable definition node."""
    var_name = var_def_node.variable.name.value
    var_type = type_from_ast(schema, var_def_node.type)

    if not is_input_type(var_type):
        # Must use input types for variables. This should be caught during
        # validation, however is checked again here for safety.
        var_type_str = print_ast(var_def_node.type)
        return GraphQLError(
            f"Variable '${var_name}' expected value of type '{var_type_str}'"
            " which cannot be used as an input type.",
            var_def_node.type,
        )

    return GraphQLVariableSignature(
        name=var_name,
        type=var_type,
        default_value=value_from_ast(var_def_node.default_value, var_type),
    )
