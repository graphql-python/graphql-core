"""Replacing variables in an AST value with their literal values"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..language import (
    ConstValueNode,
    ListValueNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    ValueNode,
    VariableNode,
)
from ..pyutils import Undefined
from .value_to_literal import value_to_literal

if TYPE_CHECKING:
    from ..execution.values import (
        FragmentVariableValues,
        FragmentVariableValueSource,
        VariableValues,
        VariableValueSource,
    )

__all__ = ["replace_variables"]


def replace_variables(
    value_node: ValueNode,
    variable_values: VariableValues | None = None,
    fragment_variable_values: FragmentVariableValues | None = None,
) -> ConstValueNode:
    """Replace any variables in an AST value with literal values.

    Replaces any variables found within an AST value literal with literals
    supplied from a map of variable values, or removes them if no variable
    replacement exists, returning a constant value.

    Used primarily to ensure only complete constant values are used during input
    coercion of custom scalars which accept complex literals.
    """
    if isinstance(value_node, VariableNode):
        var_name = value_node.name.value
        fragment_variable_value_source = (
            fragment_variable_values.sources.get(var_name)
            if fragment_variable_values
            else None
        )

        if fragment_variable_value_source is not None:
            value = fragment_variable_value_source.value
            if value is Undefined:
                default = fragment_variable_value_source.signature.default
                if default is not None:
                    return cast("ConstValueNode", default.literal)
                return NullValueNode()
            return replace_variables(
                value,
                variable_values,
                fragment_variable_value_source.fragment_variable_values,
            )

        variable_value_source = (
            variable_values.sources.get(var_name) if variable_values else None
        )
        if variable_value_source is None:
            return NullValueNode()

        if variable_value_source.value is Undefined:
            default = variable_value_source.signature.default
            if default is not None:
                return cast("ConstValueNode", default.literal)

        return cast(
            "ConstValueNode",
            value_to_literal(
                variable_value_source.value, variable_value_source.signature.type
            ),
        )

    if isinstance(value_node, ObjectValueNode):
        new_fields: list[ObjectFieldNode] = []
        for field in value_node.fields:
            if isinstance(field.value, VariableNode):
                field_var_name = field.value.name.value
                field_variable_source: (
                    VariableValueSource | FragmentVariableValueSource | None
                ) = None
                if (
                    fragment_variable_values
                    and field_var_name in fragment_variable_values.sources
                ):
                    field_variable_source = fragment_variable_values.sources[
                        field_var_name
                    ]
                elif variable_values and field_var_name in variable_values.sources:
                    field_variable_source = variable_values.sources[field_var_name]

                if field_variable_source is None or (
                    field_variable_source.value is Undefined
                    and field_variable_source.signature.default is None
                ):
                    continue
            new_field_node_value = replace_variables(
                field.value, variable_values, fragment_variable_values
            )
            new_fields.append(
                ObjectFieldNode(name=field.name, value=new_field_node_value)
            )
        return cast("ConstValueNode", ObjectValueNode(fields=tuple(new_fields)))

    if isinstance(value_node, ListValueNode):
        new_values: list[ConstValueNode] = []
        for value in value_node.values:
            new_item_node_value = replace_variables(
                value, variable_values, fragment_variable_values
            )
            new_values.append(new_item_node_value)
        return cast("ConstValueNode", ListValueNode(values=tuple(new_values)))

    return cast("ConstValueNode", value_node)
