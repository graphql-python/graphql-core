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
