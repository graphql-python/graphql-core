"""Input value coercion"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..language import (
    ListValueNode,
    NullValueNode,
    ObjectValueNode,
    ValueNode,
    VariableNode,
)
from ..pyutils import (
    Undefined,
    inspect,
    is_iterable,
)
from ..type import (
    GraphQLDefaultValueUsage,
    GraphQLInputType,
    assert_leaf_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_required_input_field,
)
from .replace_variables import replace_variables

if TYPE_CHECKING:
    from ..execution.values import VariableValues

__all__ = ["coerce_default_value", "coerce_input_literal", "coerce_input_value"]


def coerce_input_value(input_value: Any, type_: GraphQLInputType) -> Any:
    """Coerce a Python value given a GraphQL Input Type.

    Returns ``Undefined`` when the value could not be validly coerced according
    to the provided type.
    """
    if is_non_null_type(type_):
        if input_value is None or input_value is Undefined:
            return Undefined  # Invalid: intentionally return no value.
        return coerce_input_value(input_value, type_.of_type)

    if input_value is None or input_value is Undefined:
        return None  # Explicitly return the value null.

    if is_list_type(type_):
        item_type = type_.of_type
        if not is_iterable(input_value):
            # Lists accept a non-list value as a list of one.
            coerced_item = coerce_input_value(input_value, item_type)
            if coerced_item is Undefined:
                return Undefined  # Invalid: intentionally return no value.
            return [coerced_item]
        coerced_list: list[Any] = []
        append_item = coerced_list.append
        for item_value in input_value:
            coerced_item = coerce_input_value(item_value, item_type)
            if coerced_item is Undefined:
                return Undefined  # Invalid: intentionally return no value.
            append_item(coerced_item)
        return coerced_list

    if is_input_object_type(type_):
        if not isinstance(input_value, dict):
            return Undefined  # Invalid: intentionally return no value.

        coerced_dict: dict[str, Any] = {}
        fields = type_.fields
        if any(field_name not in fields for field_name in input_value):
            return Undefined  # Invalid: intentionally return no value.
        for field_name, field in fields.items():
            field_value = input_value.get(field_name, Undefined)
            if field_value is Undefined:
                if is_required_input_field(field):
                    return Undefined  # Invalid: intentionally return no value.
                if field.default_value:
                    # Use out name as name if it exists (extension of GraphQL.js).
                    coerced_dict[field.out_name or field_name] = coerce_default_value(
                        field.default_value, field.type
                    )
            else:
                coerced_field = coerce_input_value(field_value, field.type)
                if coerced_field is Undefined:
                    return Undefined  # Invalid: intentionally return no value.
                coerced_dict[field.out_name or field_name] = coerced_field

        if type_.is_one_of:
            keys = list(coerced_dict)
            if len(keys) != 1:
                # Invalid: not exactly one key, intentionally return no value.
                return Undefined
            if coerced_dict[keys[0]] is None:
                # Invalid: value not non-null, intentionally return no value.
                return Undefined

        return type_.out_type(coerced_dict)

    leaf_type = assert_leaf_type(type_)
    try:
        return leaf_type.coerce_input_value(input_value)
    except Exception:  # noqa: BLE001
        # Invalid: ignore error and intentionally return no value.
        return Undefined


def coerce_input_literal(
    value_node: ValueNode,
    type_: GraphQLInputType,
    variable_values: VariableValues | None = None,
    fragment_variable_values: VariableValues | None = None,
) -> Any:
    """Produce a coerced Python value given a GraphQL Value AST.

    Returns ``Undefined`` when the value could not be validly coerced according
    to the provided type.

    Unlike :func:`~graphql.utilities.value_from_ast`, this properly supports
    fragment variables in addition to operation variables.
    """
    if isinstance(value_node, VariableNode):
        variable_value = get_coerced_variable_value(
            value_node, variable_values, fragment_variable_values
        )
        if (variable_value is None or variable_value is Undefined) and is_non_null_type(
            type_
        ):
            return Undefined  # Invalid: intentionally return no value.
        # Note: This does no further checking that this variable is correct.
        # This assumes validation has checked this variable is of the correct type.
        return variable_value

    if is_non_null_type(type_):
        if isinstance(value_node, NullValueNode):
            return Undefined  # Invalid: intentionally return no value.
        return coerce_input_literal(
            value_node,
            type_.of_type,
            variable_values,
            fragment_variable_values,
        )

    if isinstance(value_node, NullValueNode):
        return None  # Explicitly return the value null.

    if is_list_type(type_):
        item_type = type_.of_type
        if not isinstance(value_node, ListValueNode):
            # Lists accept a non-list value as a list of one.
            item_value = coerce_input_literal(
                value_node,
                item_type,
                variable_values,
                fragment_variable_values,
            )
            if item_value is Undefined:
                return Undefined  # Invalid: intentionally return no value.
            return [item_value]
        coerced_list: list[Any] = []
        for item_node in value_node.values:
            item_value = coerce_input_literal(
                item_node,
                item_type,
                variable_values,
                fragment_variable_values,
            )
            if item_value is Undefined:
                if (
                    isinstance(item_node, VariableNode)
                    and not is_non_null_type(item_type)
                    and _variable_value_is_null(
                        item_node, variable_values, fragment_variable_values
                    )
                ):
                    # A missing variable within a list is coerced to null.
                    coerced_list.append(None)
                    continue
                return Undefined  # Invalid: intentionally return no value.
            coerced_list.append(item_value)
        return coerced_list

    if is_input_object_type(type_):
        if not isinstance(value_node, ObjectValueNode):
            return Undefined  # Invalid: intentionally return no value.

        coerced_dict: dict[str, Any] = {}
        field_defs = type_.fields
        field_nodes = {field.name.value: field for field in value_node.fields}
        # Ensure every provided field is defined.
        if any(field_name not in field_defs for field_name in field_nodes):
            return Undefined  # Invalid: intentionally return no value.
        for field_name, field in field_defs.items():
            field_node = field_nodes.get(field_name)
            if field_node is None or (
                isinstance(field_node.value, VariableNode)
                and _variable_value_is_null(
                    field_node.value, variable_values, fragment_variable_values
                )
            ):
                if is_required_input_field(field):
                    return Undefined  # Invalid: intentionally return no value.
                if field.default_value:
                    # Use out name as name if it exists (extension of GraphQL.js).
                    coerced_dict[field.out_name or field_name] = coerce_default_value(
                        field.default_value, field.type
                    )
            else:
                field_value = coerce_input_literal(
                    field_node.value,
                    field.type,
                    variable_values,
                    fragment_variable_values,
                )
                if field_value is Undefined:
                    return Undefined  # Invalid: intentionally return no value.
                coerced_dict[field.out_name or field_name] = field_value

        if type_.is_one_of:
            keys = list(coerced_dict)
            if len(keys) != 1:
                # Invalid: not exactly one key, intentionally return no value.
                return Undefined
            if coerced_dict[keys[0]] is None:
                # Invalid: value not non-null, intentionally return no value.
                return Undefined

        return type_.out_type(coerced_dict)

    leaf_type = assert_leaf_type(type_)
    try:
        if leaf_type.coerce_input_literal is not None:
            return leaf_type.coerce_input_literal(
                replace_variables(value_node, variable_values, fragment_variable_values)
            )
        return leaf_type.parse_literal(
            value_node, variable_values.coerced if variable_values else None
        )
    except Exception:  # noqa: BLE001
        # Invalid: ignore error and intentionally return no value.
        return Undefined


def coerce_default_value(
    default_value: GraphQLDefaultValueUsage,
    type_: GraphQLInputType,
) -> Any:
    """Coerce a default value usage to a Python value.

    .. internal::
    """
    # Memoize the result of coercing the default value in a hidden field.
    coerced_value = default_value._memoized_coerced_value  # noqa: SLF001
    if coerced_value is Undefined:
        coerced_value = (
            coerce_input_literal(default_value.literal, type_)
            if default_value.literal is not None
            else coerce_input_value(default_value.value, type_)
        )
        if coerced_value is Undefined:  # pragma: no cover
            msg = f"Invalid default value: {inspect(default_value)}"
            raise TypeError(msg)
        default_value._memoized_coerced_value = coerced_value  # noqa: SLF001
    return coerced_value


def get_coerced_variable_value(
    variable_node: VariableNode,
    variable_values: VariableValues | None,
    fragment_variable_values: VariableValues | None,
) -> Any:
    """Retrieve the coerced variable value for the given variable node."""
    var_name = variable_node.name.value
    if fragment_variable_values and var_name in fragment_variable_values.sources:
        return fragment_variable_values.coerced.get(var_name, Undefined)
    if variable_values:
        return variable_values.coerced.get(var_name, Undefined)
    return Undefined


def _variable_value_is_null(
    variable_node: VariableNode,
    variable_values: VariableValues | None,
    fragment_variable_values: VariableValues | None,
) -> bool:
    """Check whether the given variable node resolves to null or undefined."""
    variable_value = get_coerced_variable_value(
        variable_node, variable_values, fragment_variable_values
    )
    return variable_value is None or variable_value is Undefined
