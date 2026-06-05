"""Replacing variables in an AST value with their literal values"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..language import (
    ConstValueNode,
    NullValueNode,
    ValueNode,
    VariableNode,
    Visitor,
    visit,
)
from ..pyutils import Undefined
from .value_to_literal import value_to_literal

if TYPE_CHECKING:
    from ..execution.values import VariableValues

__all__ = ["replace_variables"]


def replace_variables(
    value_node: ValueNode,
    variable_values: VariableValues | None = None,
    fragment_variable_values: VariableValues | None = None,
) -> ConstValueNode:
    """Replace any variables in an AST value with literal values.

    Replaces any variables found within an AST value literal with literals
    supplied from a map of variable values, or removes them if no variable
    replacement exists, returning a constant value.

    Used primarily to ensure only complete constant values are used during input
    coercion of custom scalars which accept complex literals.
    """
    visitor = _ReplaceVariablesVisitor(variable_values, fragment_variable_values)
    return cast("ConstValueNode", visit(value_node, visitor))


class _ReplaceVariablesVisitor(Visitor):
    """A visitor that replaces variable nodes with their literal values."""

    def __init__(
        self,
        variable_values: VariableValues | None,
        fragment_variable_values: VariableValues | None,
    ) -> None:
        super().__init__()
        self.variable_values = variable_values
        self.fragment_variable_values = fragment_variable_values

    def enter_variable(
        self, node: VariableNode, *_args: object
    ) -> ConstValueNode | None:
        var_name = node.name.value
        fragment_variable_values = self.fragment_variable_values
        scoped_variable_values = (
            fragment_variable_values
            if fragment_variable_values and var_name in fragment_variable_values.sources
            else self.variable_values
        )

        if scoped_variable_values is None:
            return NullValueNode()

        scoped_variable_source = scoped_variable_values.sources[var_name]
        if scoped_variable_source.value is Undefined:
            default_value = scoped_variable_source.signature.default_value
            if default_value is not Undefined:
                return default_value.literal

        return value_to_literal(
            scoped_variable_source.value, scoped_variable_source.signature.type
        )

    def enter_object_value(self, node: object, *_args: object) -> object:
        variable_values = self.variable_values
        fragment_variable_values = self.fragment_variable_values
        # Filter out any fields with a missing variable.
        fields = []
        for field in node.fields:  # type: ignore
            if not isinstance(field.value, VariableNode):
                fields.append(field)
                continue
            var_name = field.value.name.value
            scoped_variable_source = None
            if (
                fragment_variable_values
                and var_name in fragment_variable_values.sources
            ):
                scoped_variable_source = fragment_variable_values.sources[var_name]
            elif variable_values and var_name in variable_values.sources:
                scoped_variable_source = variable_values.sources[var_name]
            if scoped_variable_source is not None and not (
                scoped_variable_source.value is Undefined
                and scoped_variable_source.signature.default_value is Undefined
            ):
                fields.append(field)
        if len(fields) == len(node.fields):  # type: ignore
            return None  # No fields removed, keep the node unchanged.
        return node.__class__(fields=tuple(fields))  # type: ignore
