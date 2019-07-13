from typing import Any, Dict, List, Optional, cast

from ..error import INVALID
from ..language import (
    EnumValueNode,
    ListValueNode,
    NullValueNode,
    ObjectValueNode,
    ValueNode,
    VariableNode,
)
from ..pyutils import inspect, is_invalid
from ..type import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    is_enum_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_scalar_type,
)

__all__ = ["value_from_ast"]


def value_from_ast(
    value_node: Optional[ValueNode],
    type_: GraphQLInputType,
    variables: Dict[str, Any] = None,
) -> Any:
    """Produce a Python value given a GraphQL Value AST.

    A GraphQL type must be provided, which will be used to interpret different GraphQL
    Value literals.

    Returns `INVALID` when the value could not be validly coerced according
    to the provided type.

    | GraphQL Value        | JSON Value    | Python Value |
    | -------------------- | ------------- | ------------ |
    | Input Object         | Object        | dict         |
    | List                 | Array         | list         |
    | Boolean              | Boolean       | bool         |
    | String               | String        | str          |
    | Int / Float          | Number        | int / float  |
    | Enum Value           | Mixed         | Any          |
    | NullValue            | null          | None         |

    """
    if not value_node:
        # When there is no node, then there is also no value.
        # Importantly, this is different from returning the value null.
        return INVALID

    if is_non_null_type(type_):
        if isinstance(value_node, NullValueNode):
            return INVALID
        type_ = cast(GraphQLNonNull, type_)
        return value_from_ast(value_node, type_.of_type, variables)

    if isinstance(value_node, NullValueNode):
        return None  # This is explicitly returning the value None.

    if isinstance(value_node, VariableNode):
        variable_name = value_node.name.value
        if not variables:
            return INVALID
        variable_value = variables.get(variable_name, INVALID)
        if is_invalid(variable_value):
            return INVALID
        if variable_value is None and is_non_null_type(type_):
            return INVALID
        # Note: This does no further checking that this variable is correct.
        # This assumes that this query has been validated and the variable usage here
        # is of the correct type.
        return variable_value

    if is_list_type(type_):
        type_ = cast(GraphQLList, type_)
        item_type = type_.of_type
        if isinstance(value_node, ListValueNode):
            coerced_values: List[Any] = []
            append_value = coerced_values.append
            for item_node in value_node.values:
                if is_missing_variable(item_node, variables):
                    # If an array contains a missing variable, it is either coerced to
                    # None or if the item type is non-null, it is considered invalid.
                    if is_non_null_type(item_type):
                        return INVALID
                    append_value(None)
                else:
                    item_value = value_from_ast(item_node, item_type, variables)
                    if is_invalid(item_value):
                        return INVALID
                    append_value(item_value)
            return coerced_values
        coerced_value = value_from_ast(value_node, item_type, variables)
        if is_invalid(coerced_value):
            return INVALID
        return [coerced_value]

    if is_input_object_type(type_):
        if not isinstance(value_node, ObjectValueNode):
            return INVALID
        type_ = cast(GraphQLInputObjectType, type_)
        coerced_obj: Dict[str, Any] = {}
        fields = type_.fields
        field_nodes = {field.name.value: field for field in value_node.fields}
        for field_name, field in fields.items():
            field_node = field_nodes.get(field_name)
            if not field_node or is_missing_variable(field_node.value, variables):
                if field.default_value is not INVALID:
                    # Use out name as name if it exists (extension of GraphQL.js).
                    coerced_obj[field.out_name or field_name] = field.default_value
                elif is_non_null_type(field.type):
                    return INVALID
                continue
            field_value = value_from_ast(field_node.value, field.type, variables)
            if is_invalid(field_value):
                return INVALID
            coerced_obj[field.out_name or field_name] = field_value

        return type_.out_type(coerced_obj)

    if is_enum_type(type_):
        if not isinstance(value_node, EnumValueNode):
            return INVALID
        type_ = cast(GraphQLEnumType, type_)
        enum_value = type_.values.get(value_node.value)
        if not enum_value:
            return INVALID
        return enum_value.value

    if is_scalar_type(type_):
        # Scalars fulfill parsing a literal value via `parse_literal()`. Invalid values
        # represent a failure to parse correctly, in which case INVALID is returned.
        type_ = cast(GraphQLScalarType, type_)
        try:
            if variables:
                result = type_.parse_literal(value_node, variables)
            else:
                result = type_.parse_literal(value_node)
        except (ArithmeticError, TypeError, ValueError):
            return INVALID
        if is_invalid(result):
            return INVALID
        return result

    # Not reachable. All possible input types have been considered.
    raise TypeError(f"Unexpected input type: '{inspect(type_)}'.")  # pragma: no cover


def is_missing_variable(
    value_node: ValueNode, variables: Dict[str, Any] = None
) -> bool:
    """Check if `value_node` is a variable not defined in the `variables` dict."""
    return isinstance(value_node, VariableNode) and (
        not variables or is_invalid(variables.get(value_node.name.value, INVALID))
    )
