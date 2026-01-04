"""Conversion from GraphQL value AST to Python values without type."""

from __future__ import annotations

from math import nan
from typing import TYPE_CHECKING, Any

from ..pyutils import Undefined, inspect

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..language import (
        BooleanValueNode,
        EnumValueNode,
        FloatValueNode,
        IntValueNode,
        ListValueNode,
        NullValueNode,
        ObjectValueNode,
        StringValueNode,
        ValueNode,
        VariableNode,
    )

__all__ = ["value_from_ast_untyped"]


def value_from_ast_untyped(
    value_node: ValueNode, variables: dict[str, Any] | None = None
) -> Any:
    """Produce a Python value given a GraphQL Value AST.

    Unlike :func:`~graphql.utilities.value_from_ast`, no type is provided.
    The resulting Python value will reflect the provided GraphQL value AST.

    =================== ============== ================
       GraphQL Value      JSON Value     Python Value
    =================== ============== ================
       Input Object       Object         dict
       List               Array          list
       Boolean            Boolean        bool
       String / Enum      String         str
       Int / Float        Number         int / float
       Null               null           None
    =================== ============== ================

    """
    func = _value_from_kind_functions.get(value_node.kind)
    if func:
        return func(value_node, variables)

    # Not reachable. All possible value nodes have been considered.
    msg = f"Unexpected value node: {inspect(value_node)}."  # pragma: no cover
    raise TypeError(msg)  # pragma: no cover


def value_from_null(_value_node: NullValueNode, _variables: Any) -> Any:
    return None


def value_from_int(value_node: IntValueNode, _variables: Any) -> Any:
    try:
        return int(value_node.value)
    except ValueError:
        return nan


def value_from_float(value_node: FloatValueNode, _variables: Any) -> Any:
    try:
        return float(value_node.value)
    except ValueError:
        return nan


def value_from_string(
    value_node: BooleanValueNode | EnumValueNode | StringValueNode, _variables: Any
) -> Any:
    return value_node.value


def value_from_list(value_node: ListValueNode, variables: dict[str, Any] | None) -> Any:
    return [value_from_ast_untyped(node, variables) for node in value_node.values]


def value_from_object(
    value_node: ObjectValueNode, variables: dict[str, Any] | None
) -> Any:
    return {
        field.name.value: value_from_ast_untyped(field.value, variables)
        for field in value_node.fields
    }


def value_from_variable(
    value_node: VariableNode, variables: dict[str, Any] | None
) -> Any:
    variable_name = value_node.name.value
    if not variables:
        return Undefined
    return variables.get(variable_name, Undefined)


_value_from_kind_functions: dict[str, Callable] = {
    "null_value": value_from_null,
    "int_value": value_from_int,
    "float_value": value_from_float,
    "string_value": value_from_string,
    "enum_value": value_from_string,
    "boolean_value": value_from_string,
    "list_value": value_from_list,
    "object_value": value_from_object,
    "variable": value_from_variable,
}
