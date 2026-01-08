"""Sorting value nodes"""

from __future__ import annotations

from ..language import ListValueNode, ObjectFieldNode, ObjectValueNode, ValueNode
from ..pyutils import natural_comparison_key

__all__ = ["sort_value_node"]


def sort_value_node(value_node: ValueNode) -> ValueNode:
    """Sort ValueNode.

    This function returns a sorted copy of the given ValueNode

    For internal use only.
    """
    if isinstance(value_node, ObjectValueNode):
        # Create new node with updated fields (immutable-friendly copy-on-write)
        values = {k: getattr(value_node, k) for k in value_node.keys}
        values["fields"] = sort_fields(value_node.fields)
        value_node = value_node.__class__(**values)
    elif isinstance(value_node, ListValueNode):
        # Create new node with updated values (immutable-friendly copy-on-write)
        values = {k: getattr(value_node, k) for k in value_node.keys}
        values["values"] = tuple(sort_value_node(value) for value in value_node.values)
        value_node = value_node.__class__(**values)
    return value_node


def sort_field(field: ObjectFieldNode) -> ObjectFieldNode:
    # Create new node with updated value (immutable-friendly copy-on-write)
    values = {k: getattr(field, k) for k in field.keys}
    values["value"] = sort_value_node(field.value)
    return field.__class__(**values)


def sort_fields(fields: tuple[ObjectFieldNode, ...]) -> tuple[ObjectFieldNode, ...]:
    return tuple(
        sorted(
            (sort_field(field) for field in fields),
            key=lambda field: natural_comparison_key(field.name.value),
        )
    )
