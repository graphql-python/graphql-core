"""Collect fields"""

from __future__ import annotations

import sys
from typing import Any, Dict, NamedTuple, Union, cast

from ..language import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from ..pyutils import RefMap, RefSet
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
    "NON_DEFERRED_TARGET_SET",
    "CollectFieldsContext",
    "CollectFieldsResult",
    "DeferUsage",
    "DeferUsageSet",
    "FieldDetails",
    "FieldGroup",
    "GroupedFieldSetDetails",
    "Target",
    "TargetSet",
    "collect_fields",
    "collect_subfields",
]


class DeferUsage(NamedTuple):
    """An optionally labelled list of ancestor targets."""

    label: str | None
    ancestors: list[Target]


Target: TypeAlias = Union[DeferUsage, None]

TargetSet: TypeAlias = RefSet[Target]
DeferUsageSet: TypeAlias = RefSet[DeferUsage]


NON_DEFERRED_TARGET_SET: TargetSet = RefSet([None])


class FieldDetails(NamedTuple):
    """A field node and its target."""

    node: FieldNode
    target: Target


class FieldGroup(NamedTuple):
    """A group of fields that share the same target set."""

    fields: list[FieldDetails]
    targets: TargetSet

    def to_nodes(self) -> list[FieldNode]:
        """Return the field nodes in this group."""
        return [field_details.node for field_details in self.fields]


if sys.version_info < (3, 9):
    GroupedFieldSet: TypeAlias = Dict[str, FieldGroup]
else:  # Python >= 3.9
    GroupedFieldSet: TypeAlias = dict[str, FieldGroup]


class GroupedFieldSetDetails(NamedTuple):
    """A grouped field set with defer info."""

    grouped_field_set: GroupedFieldSet
    should_initiate_defer: bool


class CollectFieldsResult(NamedTuple):
    """Collected fields and deferred usages."""

    grouped_field_set: GroupedFieldSet
    new_grouped_field_set_details: RefMap[DeferUsageSet, GroupedFieldSetDetails]
    new_defer_usages: list[DeferUsage]


class CollectFieldsContext(NamedTuple):
    """Context for collecting fields."""

    schema: GraphQLSchema
    fragments: dict[str, FragmentDefinitionNode]
    variable_values: dict[str, Any]
    operation: OperationDefinitionNode
    runtime_type: GraphQLObjectType
    targets_by_key: dict[str, TargetSet]
    fields_by_target: RefMap[Target, dict[str, list[FieldNode]]]
    new_defer_usages: list[DeferUsage]
    visited_fragment_names: set[str]


def collect_fields(
    schema: GraphQLSchema,
    fragments: dict[str, FragmentDefinitionNode],
    variable_values: dict[str, Any],
    runtime_type: GraphQLObjectType,
    operation: OperationDefinitionNode,
) -> CollectFieldsResult:
    """Collect fields.

    Given a selection_set, collects all the fields and returns them.

    collect_fields requires the "runtime type" of an object. For a field that
    returns an Interface or Union type, the "runtime type" will be the actual
    object type returned by that field.

    For internal use only.
    """
    context = CollectFieldsContext(
        schema,
        fragments,
        variable_values,
        operation,
        runtime_type,
        {},
        RefMap(),
        [],
        set(),
    )
    collect_fields_impl(context, operation.selection_set)

    return CollectFieldsResult(
        *build_grouped_field_sets(context.targets_by_key, context.fields_by_target),
        context.new_defer_usages,
    )


def collect_subfields(
    schema: GraphQLSchema,
    fragments: dict[str, FragmentDefinitionNode],
    variable_values: dict[str, Any],
    operation: OperationDefinitionNode,
    return_type: GraphQLObjectType,
    field_group: FieldGroup,
) -> CollectFieldsResult:
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
        {},
        RefMap(),
        [],
        set(),
    )

    for field_details in field_group.fields:
        node = field_details.node
        if node.selection_set:
            collect_fields_impl(context, node.selection_set, field_details.target)

    return CollectFieldsResult(
        *build_grouped_field_sets(
            context.targets_by_key, context.fields_by_target, field_group.targets
        ),
        context.new_defer_usages,
    )


def collect_fields_impl(
    context: CollectFieldsContext,
    selection_set: SelectionSetNode,
    parent_target: Target | None = None,
    new_target: Target | None = None,
) -> None:
    """Collect fields (internal implementation)."""
    (
        schema,
        fragments,
        variable_values,
        operation,
        runtime_type,
        targets_by_key,
        fields_by_target,
        new_defer_usages,
        visited_fragment_names,
    ) = context

    ancestors: list[Target]

    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            if not should_include_node(variable_values, selection):
                continue
            key = get_field_entry_key(selection)
            target = new_target or parent_target
            key_targets = targets_by_key.get(key)
            if key_targets is None:
                key_targets = RefSet([target])
                targets_by_key[key] = key_targets
            else:
                key_targets.add(target)
            target_fields = fields_by_target.get(target)
            if target_fields is None:
                fields_by_target[target] = {key: [selection]}
            else:
                field_nodes = target_fields.get(key)
                if field_nodes is None:
                    target_fields[key] = [selection]
                else:
                    field_nodes.append(selection)
        elif isinstance(selection, InlineFragmentNode):
            if not should_include_node(
                variable_values, selection
            ) or not does_fragment_condition_match(schema, selection, runtime_type):
                continue

            defer = get_defer_values(operation, variable_values, selection)

            if defer:
                ancestors = (
                    [None]
                    if parent_target is None
                    else [parent_target, *parent_target.ancestors]
                )
                target = DeferUsage(defer.label, ancestors)
                new_defer_usages.append(target)
            else:
                target = new_target

            collect_fields_impl(context, selection.selection_set, parent_target, target)
        elif isinstance(selection, FragmentSpreadNode):  # pragma: no cover else
            frag_name = selection.name.value

            if not should_include_node(variable_values, selection):
                continue

            defer = get_defer_values(operation, variable_values, selection)
            if frag_name in visited_fragment_names and not defer:
                continue

            fragment = fragments.get(frag_name)
            if not fragment or not does_fragment_condition_match(
                schema, fragment, runtime_type
            ):
                continue

            if defer:
                ancestors = (
                    [None]
                    if parent_target is None
                    else [parent_target, *parent_target.ancestors]
                )
                target = DeferUsage(defer.label, ancestors)
                new_defer_usages.append(target)
            else:
                visited_fragment_names.add(frag_name)
                target = new_target

            collect_fields_impl(context, fragment.selection_set, parent_target, target)


class DeferValues(NamedTuple):
    """Values of an active defer directive."""

    label: str | None


def get_defer_values(
    operation: OperationDefinitionNode,
    variable_values: dict[str, Any],
    node: FragmentSpreadNode | InlineFragmentNode,
) -> DeferValues | None:
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

    return DeferValues(defer.get("label"))


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


def build_grouped_field_sets(
    targets_by_key: dict[str, TargetSet],
    fields_by_target: RefMap[Target, dict[str, list[FieldNode]]],
    parent_targets: TargetSet = NON_DEFERRED_TARGET_SET,
) -> tuple[GroupedFieldSet, RefMap[DeferUsageSet, GroupedFieldSetDetails]]:
    """Build grouped field sets."""
    parent_target_keys, target_set_details_map = get_target_set_details(
        targets_by_key, parent_targets
    )

    grouped_field_set = (
        get_ordered_grouped_field_set(
            parent_target_keys, parent_targets, targets_by_key, fields_by_target
        )
        if parent_target_keys
        else {}
    )

    new_grouped_field_set_details: RefMap[DeferUsageSet, GroupedFieldSetDetails] = (
        RefMap()
    )

    for masking_targets, target_set_details in target_set_details_map.items():
        keys, should_initiate_defer = target_set_details

        new_grouped_field_set = get_ordered_grouped_field_set(
            keys, masking_targets, targets_by_key, fields_by_target
        )

        # All TargetSets that causes new grouped field sets consist only of DeferUsages
        # and have should_initiate_defer defined

        new_grouped_field_set_details[cast(DeferUsageSet, masking_targets)] = (
            GroupedFieldSetDetails(new_grouped_field_set, should_initiate_defer)
        )

    return grouped_field_set, new_grouped_field_set_details


class TargetSetDetails(NamedTuple):
    """A set of target keys with defer info."""

    keys: set[str]
    should_initiate_defer: bool


def get_target_set_details(
    targets_by_key: dict[str, TargetSet], parent_targets: TargetSet
) -> tuple[set[str], RefMap[TargetSet, TargetSetDetails]]:
    """Get target set details."""
    parent_target_keys: set[str] = set()
    target_set_details_map: RefMap[TargetSet, TargetSetDetails] = RefMap()

    for response_key, targets in targets_by_key.items():
        masking_target_list: list[Target] = []
        for target in targets:
            if not target or all(
                ancestor not in targets for ancestor in target.ancestors
            ):
                masking_target_list.append(target)

        masking_targets: TargetSet = RefSet(masking_target_list)
        if masking_targets == parent_targets:
            parent_target_keys.add(response_key)
            continue

        for target_set, target_set_details in target_set_details_map.items():
            if target_set == masking_targets:
                target_set_details.keys.add(response_key)
                break
        else:
            target_set_details = TargetSetDetails(
                {response_key},
                any(
                    defer_usage not in parent_targets for defer_usage in masking_targets
                ),
            )
            target_set_details_map[masking_targets] = target_set_details

    return parent_target_keys, target_set_details_map


def get_ordered_grouped_field_set(
    keys: set[str],
    masking_targets: TargetSet,
    targets_by_key: dict[str, TargetSet],
    fields_by_target: RefMap[Target, dict[str, list[FieldNode]]],
) -> GroupedFieldSet:
    """Get ordered grouped field set."""
    grouped_field_set: GroupedFieldSet = {}

    first_target = next(iter(masking_targets))
    first_fields = fields_by_target[first_target]
    for key in list(first_fields):
        if key in keys:
            field_group = grouped_field_set.get(key)
            if field_group is None:  # pragma: no cover else
                field_group = FieldGroup([], masking_targets)
                grouped_field_set[key] = field_group
            for target in targets_by_key[key]:
                fields_for_target = fields_by_target[target]
                nodes = fields_for_target[key]
                del fields_for_target[key]
                field_group.fields.extend(FieldDetails(node, target) for node in nodes)

    return grouped_field_set
