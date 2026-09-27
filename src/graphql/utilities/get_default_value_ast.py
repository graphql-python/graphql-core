"""Getting the AST of a default value"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..pyutils import Undefined
from .ast_from_value import ast_from_value
from .value_to_literal import value_to_literal

if TYPE_CHECKING:
    from ..language import ConstValueNode
    from ..type import GraphQLArgument, GraphQLInputField

__all__ = ["get_default_value_ast"]


def get_default_value_ast(
    arg_or_input_field: GraphQLArgument | GraphQLInputField,
) -> ConstValueNode | None:
    """Get the AST of the default value of an argument or input field.

    Returns ``None`` if no default value is provided.

    Both external defaults (``default``, given as a runtime value or as a literal)
    and deprecated internal defaults (``default_value``) are supported.

    :param arg_or_input_field: The argument or input field to inspect.
    :returns: The default value as a constant value AST node, or ``None``.

    >>> from graphql import (
    ...     GraphQLArgument,
    ...     GraphQLDefaultInput,
    ...     GraphQLInt,
    ...     GraphQLList,
    ...     build_schema,
    ...     print_ast,
    ... )
    >>> from graphql.utilities import get_default_value_ast
    >>> schema = build_schema('''
    ...   type Query {
    ...     greet(name: String = "Ada", times: Int): String
    ...   }
    ... ''')
    >>> args = schema.query_type.fields['greet'].args
    >>> print_ast(get_default_value_ast(args['name']))
    '"Ada"'
    >>> get_default_value_ast(args['times']) is None
    True
    >>> argument = GraphQLArgument(
    ...     GraphQLList(GraphQLInt), default=GraphQLDefaultInput([1, 2])
    ... )
    >>> print_ast(get_default_value_ast(argument))
    '[1, 2]'
    """
    type_ = arg_or_input_field.type
    default_input = arg_or_input_field.default
    if default_input is not None:
        literal = (
            default_input.literal
            if default_input.literal is not None
            else value_to_literal(default_input.value, type_)
        )
        if literal is None:  # pragma: no cover
            msg = "Invalid default value"
            raise TypeError(msg)
        return literal

    default_value = arg_or_input_field.default_value
    if default_value is not Undefined:
        value_ast = ast_from_value(default_value, type_)
        if value_ast is None:  # pragma: no cover
            msg = "Invalid default value"
            raise TypeError(msg)
        return value_ast
    return None
