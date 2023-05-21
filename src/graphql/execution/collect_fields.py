from collections import defaultdict
from typing import Any, Dict, List, NamedTuple, Optional, Set, Union

from ..language import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
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


__all__ = ["collect_fields", "collect_subfields", "FieldsAndPatches"]


class PatchFields(NamedTuple):
    """Optionally labelled set of fields to be used as a patch."""

    label: Optional[str]
    fields: Dict[str, List[FieldNode]]


class FieldsAndPatches(NamedTuple):
    """Tuple of collected fields and patches to be applied."""

    fields: Dict[str, List[FieldNode]]
    patches: List[PatchFields]


def collect_fields(
    schema: GraphQLSchema,
    fragments: Dict[str, FragmentDefinitionNode],
    variable_values: Dict[str, Any],
    runtime_type: GraphQLObjectType,
    selection_set: SelectionSetNode,
) -> FieldsAndPatches:
    """Collect fields.

    Given a selection_set, collects all the fields and returns them.

    collect_fields requires the "runtime type" of an object. For a field that
    returns an Interface or Union type, the "runtime type" will be the actual
    object type returned by that field.

    For internal use only.
    """
    fields: Dict[str, List[FieldNode]] = defaultdict(list)
    patches: List[PatchFields] = []
    collect_fields_impl(
        schema,
        fragments,
        variable_values,
        runtime_type,
        selection_set,
        fields,
        patches,
        set(),
    )
    return FieldsAndPatches(fields, patches)


def collect_subfields(
    schema: GraphQLSchema,
    fragments: Dict[str, FragmentDefinitionNode],
    variable_values: Dict[str, Any],
    return_type: GraphQLObjectType,
    field_nodes: List[FieldNode],
) -> FieldsAndPatches:
    """Collect subfields.

    Given a list of field nodes, collects all the subfields of the passed in fields,
    and returns them at the end.

    collect_subfields requires the "return type" of an object. For a field that
    returns an Interface or Union type, the "return type" will be the actual
    object type returned by that field.

    For internal use only.
    """
    sub_field_nodes: Dict[str, List[FieldNode]] = defaultdict(list)
    visited_fragment_names: Set[str] = set()

    sub_patches: List[PatchFields] = []
    sub_fields_and_patches = FieldsAndPatches(sub_field_nodes, sub_patches)

    for node in field_nodes:
        if node.selection_set:
            collect_fields_impl(
                schema,
                fragments,
                variable_values,
                return_type,
                node.selection_set,
                sub_field_nodes,
                sub_patches,
                visited_fragment_names,
            )
    return sub_fields_and_patches


def collect_fields_impl(
    schema: GraphQLSchema,
    fragments: Dict[str, FragmentDefinitionNode],
    variable_values: Dict[str, Any],
    runtime_type: GraphQLObjectType,
    selection_set: SelectionSetNode,
    fields: Dict[str, List[FieldNode]],
    patches: List[PatchFields],
    visited_fragment_names: Set[str],
) -> None:
    """Collect fields (internal implementation)."""
    patch_fields: Dict[str, List[FieldNode]]

    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            if not should_include_node(variable_values, selection):
                continue
            fields[get_field_entry_key(selection)].append(selection)
        elif isinstance(selection, InlineFragmentNode):
            if not should_include_node(
                variable_values, selection
            ) or not does_fragment_condition_match(schema, selection, runtime_type):
                continue

            defer = get_defer_values(variable_values, selection)
            if defer:
                patch_fields = defaultdict(list)
                collect_fields_impl(
                    schema,
                    fragments,
                    variable_values,
                    runtime_type,
                    selection.selection_set,
                    patch_fields,
                    patches,
                    visited_fragment_names,
                )
                patches.append(PatchFields(defer.label, patch_fields))
            else:
                collect_fields_impl(
                    schema,
                    fragments,
                    variable_values,
                    runtime_type,
                    selection.selection_set,
                    fields,
                    patches,
                    visited_fragment_names,
                )
        elif isinstance(selection, FragmentSpreadNode):  # pragma: no cover else
            frag_name = selection.name.value

            if not should_include_node(variable_values, selection):
                continue

            defer = get_defer_values(variable_values, selection)
            if frag_name in visited_fragment_names and not defer:
                continue

            fragment = fragments.get(frag_name)
            if not fragment or not does_fragment_condition_match(
                schema, fragment, runtime_type
            ):
                continue

            if not defer:
                visited_fragment_names.add(frag_name)

            if defer:
                patch_fields = defaultdict(list)
                collect_fields_impl(
                    schema,
                    fragments,
                    variable_values,
                    runtime_type,
                    fragment.selection_set,
                    patch_fields,
                    patches,
                    visited_fragment_names,
                )
                patches.append(PatchFields(defer.label, patch_fields))
            else:
                collect_fields_impl(
                    schema,
                    fragments,
                    variable_values,
                    runtime_type,
                    fragment.selection_set,
                    fields,
                    patches,
                    visited_fragment_names,
                )


class DeferValues(NamedTuple):
    """Values of an active defer directive."""

    label: Optional[str]


def get_defer_values(
    variable_values: Dict[str, Any], node: Union[FragmentSpreadNode, InlineFragmentNode]
) -> Optional[DeferValues]:
    """Get values of defer directive if active.

    Returns an object containing the `@defer` arguments if a field should be
    deferred based on the experimental flag, defer directive present and
    not disabled by the "if" argument.
    """
    defer = get_directive_values(GraphQLDeferDirective, node, variable_values)

    if not defer or defer.get("if") is False:
        return None

    return DeferValues(defer.get("label"))


def should_include_node(
    variable_values: Dict[str, Any],
    node: Union[FragmentSpreadNode, FieldNode, InlineFragmentNode],
) -> bool:
    """Check if node should be included

    Determines if a field should be included based on the @include and @skip
    directives, where @skip has higher precedence than @include.
    """
    skip = get_directive_values(GraphQLSkipDirective, node, variable_values)
    if skip and skip["if"]:
        return False

    include = get_directive_values(GraphQLIncludeDirective, node, variable_values)
    if include and not include["if"]:
        return False

    return True


def does_fragment_condition_match(
    schema: GraphQLSchema,
    fragment: Union[FragmentDefinitionNode, InlineFragmentNode],
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
    """Implements the logic to compute the key of a given field's entry"""
    return node.alias.value if node.alias else node.name.value
