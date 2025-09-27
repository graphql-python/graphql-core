"""Collect fields"""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import Any, NamedTuple

from ..language import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from ..type import (
    GraphQLDeferDirective,
    GraphQLIncludeDirective,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLSkipDirective,
    is_abstract_type,
)
from ..utilities.type_from_ast import type_from_ast
from .values import get_directive_values

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

__all__ = [
    "CollectFieldsContext",
    "CollectedFields",
    "DeferUsage",
    "FieldDetails",
    "FieldGroup",
    "GroupedFieldSet",
    "collect_fields",
    "collect_subfields",
]


class DeferUsage(NamedTuple):
    """An optionally labelled linked list of defer usages."""

    label: str | None
    parent_defer_usage: DeferUsage | None

    @property
    def ancestors(self) -> list[DeferUsage]:
        """Get the ancestors of this defer usage."""
        ancestors: list[DeferUsage] = []
        parent_defer_usage = self.parent_defer_usage
        while parent_defer_usage is not None:
            ancestors.append(parent_defer_usage)
            parent_defer_usage = parent_defer_usage.parent_defer_usage
        return ancestors[::-1]


class FieldDetails(NamedTuple):
    """A field node and its defer usage."""

    node: FieldNode
    defer_usage: DeferUsage | None


if sys.version_info < (3, 9):
    from typing import Dict, List

    FieldGroup: TypeAlias = List[FieldDetails]
    GroupedFieldSet: TypeAlias = Dict[str, FieldGroup]
else:  # Python >= 3.9
    FieldGroup: TypeAlias = list[FieldDetails]
    GroupedFieldSet: TypeAlias = dict[str, FieldGroup]


class CollectFieldsContext(NamedTuple):
    """Context for collecting fields."""

    schema: GraphQLSchema
    fragments: dict[str, FragmentDefinitionNode]
    variable_values: dict[str, Any]
    operation: OperationDefinitionNode
    runtime_type: GraphQLObjectType
    visited_fragment_names: set[str]


class CollectedFields(NamedTuple):
    """Collected fields with new defer usages."""

    grouped_field_set: GroupedFieldSet
    new_defer_usages: list[DeferUsage]


def collect_fields(
    schema: GraphQLSchema,
    fragments: dict[str, FragmentDefinitionNode],
    variable_values: dict[str, Any],
    runtime_type: GraphQLObjectType,
    operation: OperationDefinitionNode,
) -> CollectedFields:
    """Collect fields.

    Given a selection_set, collects all the fields and returns them.

    collect_fields requires the "runtime type" of an object. For a field that
    returns an Interface or Union type, the "runtime type" will be the actual
    object type returned by that field.

    For internal use only.
    """
    grouped_field_set: dict[str, list[FieldDetails]] = defaultdict(list)
    new_defer_usages: list[DeferUsage] = []
    context = CollectFieldsContext(
        schema,
        fragments,
        variable_values,
        operation,
        runtime_type,
        set(),
    )

    collect_fields_impl(
        context, operation.selection_set, grouped_field_set, new_defer_usages
    )
    return CollectedFields(grouped_field_set, new_defer_usages)


def collect_subfields(
    schema: GraphQLSchema,
    fragments: dict[str, FragmentDefinitionNode],
    variable_values: dict[str, Any],
    operation: OperationDefinitionNode,
    return_type: GraphQLObjectType,
    field_group: FieldGroup,
) -> CollectedFields:
    """Collect subfields.

    Given a list of field nodes, collects all the subfields of the passed in fields,
    and returns them at the end.

    collect_subfields requires the "return type" of an object. For a field that
    returns an Interface or Union type, the "return type" will be the actual
    object type returned by that field.

    For internal use only.
    """
    context = CollectFieldsContext(
        schema,
        fragments,
        variable_values,
        operation,
        return_type,
        set(),
    )
    sub_grouped_field_set: dict[str, list[FieldDetails]] = defaultdict(list)
    new_defer_usages: list[DeferUsage] = []

    for field_detail in field_group:
        node = field_detail.node
        if node.selection_set:
            collect_fields_impl(
                context,
                node.selection_set,
                sub_grouped_field_set,
                new_defer_usages,
                field_detail.defer_usage,
            )

    return CollectedFields(sub_grouped_field_set, new_defer_usages)


def collect_fields_impl(
    context: CollectFieldsContext,
    selection_set: SelectionSetNode,
    grouped_field_set: dict[str, list[FieldDetails]],
    new_defer_usages: list[DeferUsage],
    defer_usage: DeferUsage | None = None,
) -> None:
    """Collect fields (internal implementation)."""
    (
        schema,
        fragments,
        variable_values,
        operation,
        runtime_type,
        visited_fragment_names,
    ) = context

    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            if not should_include_node(variable_values, selection):
                continue
            key = get_field_entry_key(selection)
            grouped_field_set[key].append(FieldDetails(selection, defer_usage))
        elif isinstance(selection, InlineFragmentNode):
            if not should_include_node(
                variable_values, selection
            ) or not does_fragment_condition_match(schema, selection, runtime_type):
                continue

            new_defer_usage = get_defer_usage(
                operation, variable_values, selection, defer_usage
            )

            if new_defer_usage is None:
                collect_fields_impl(
                    context,
                    selection.selection_set,
                    grouped_field_set,
                    new_defer_usages,
                    defer_usage,
                )
            else:
                new_defer_usages.append(new_defer_usage)
                collect_fields_impl(
                    context,
                    selection.selection_set,
                    grouped_field_set,
                    new_defer_usages,
                    new_defer_usage,
                )
        elif isinstance(selection, FragmentSpreadNode):  # pragma: no cover else
            frag_name = selection.name.value

            new_defer_usage = get_defer_usage(
                operation, variable_values, selection, defer_usage
            )

            if new_defer_usage is None and (
                frag_name in visited_fragment_names
                or not should_include_node(variable_values, selection)
            ):
                continue

            fragment = fragments.get(frag_name)
            if fragment is None or not does_fragment_condition_match(
                schema, fragment, runtime_type
            ):
                continue

            if new_defer_usage is None:
                visited_fragment_names.add(frag_name)
                collect_fields_impl(
                    context,
                    fragment.selection_set,
                    grouped_field_set,
                    new_defer_usages,
                    defer_usage,
                )
            else:
                new_defer_usages.append(new_defer_usage)
                collect_fields_impl(
                    context,
                    fragment.selection_set,
                    grouped_field_set,
                    new_defer_usages,
                    new_defer_usage,
                )


def get_defer_usage(
    operation: OperationDefinitionNode,
    variable_values: dict[str, Any],
    node: FragmentSpreadNode | InlineFragmentNode,
    parent_defer_usage: DeferUsage | None,
) -> DeferUsage | None:
    """Get values of defer directive if active.

    Returns an object containing the `@defer` arguments if a field should be
    deferred based on the experimental flag, defer directive present and
    not disabled by the "if" argument.
    """
    defer = get_directive_values(GraphQLDeferDirective, node, variable_values)

    if not defer or defer.get("if") is False:
        return None

    if operation.operation == OperationType.SUBSCRIPTION:
        msg = (
            "`@defer` directive not supported on subscription operations."
            " Disable `@defer` by setting the `if` argument to `false`."
        )
        raise TypeError(msg)

    return DeferUsage(defer.get("label"), parent_defer_usage)


def should_include_node(
    variable_values: dict[str, Any],
    node: FragmentSpreadNode | FieldNode | InlineFragmentNode,
) -> bool:
    """Check if node should be included

    Determines if a field should be included based on the @include and @skip
    directives, where @skip has higher precedence than @include.
    """
    skip = get_directive_values(GraphQLSkipDirective, node, variable_values)
    if skip and skip["if"]:
        return False

    include = get_directive_values(GraphQLIncludeDirective, node, variable_values)
    return not (include and not include["if"])


def does_fragment_condition_match(
    schema: GraphQLSchema,
    fragment: FragmentDefinitionNode | InlineFragmentNode,
    type_: GraphQLObjectType,
) -> bool:
    """Determine if a fragment is applicable to the given type."""
    type_condition_node = fragment.type_condition
    if not type_condition_node:
        return True
    conditional_type = type_from_ast(schema, type_condition_node)
    if conditional_type is type_:
        return True
    if is_abstract_type(conditional_type):
        # noinspection PyTypeChecker
        return schema.is_sub_type(conditional_type, type_)
    return False


def get_field_entry_key(node: FieldNode) -> str:
    """Implement the logic to compute the key of a given field's entry"""
    return node.alias.value if node.alias else node.name.value
