"""Overlapping fields can be merged rule"""

from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Any, NamedTuple, TypeAlias, cast

from ...error import GraphQLError
from ...language import (
    ArgumentNode,
    DirectiveNode,
    FieldNode,
    FragmentArgumentNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    ListValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    SelectionSetNode,
    ValueNode,
    VariableNode,
    print_ast,
)
from ...type import (
    GraphQLCompositeType,
    GraphQLField,
    GraphQLNamedType,
    GraphQLOutputType,
    get_named_type,
    is_interface_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
)
from ...utilities import type_from_ast
from ...utilities.sort_value_node import sort_value_node
from . import ValidationContext, ValidationRule

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["OverlappingFieldsCanBeMergedRule"]


def reason_message(reason: ConflictReasonMessage) -> str:
    if isinstance(reason, list):
        return " and ".join(
            f"subfields '{response_name}' conflict because {reason_message(sub_reason)}"
            for response_name, sub_reason in reason
        )
    return reason


class OverlappingFieldsCanBeMergedRule(ValidationRule):
    """Overlapping fields can be merged

    A selection set is only valid if all fields (including spreading any fragments)
    either correspond to distinct response names or can be merged without ambiguity.

    See https://spec.graphql.org/draft/#sec-Field-Selection-Merging
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        # A memoization for when fields and a fragment or two fragments are compared
        # "between" each other for conflicts. Comparisons may be made many times, so
        # memoizing this can dramatically improve the performance of this validator.
        self.compared_fields_and_fragment_pairs = OrderedPairSet()
        self.compared_fragment_pairs = PairSet()

        # A cache for the "field map" and list of fragment spreads found in any given
        # selection set. Selection sets may be asked for this information multiple
        # times, so this improves the performance of this validator.
        self.cached_fields_and_fragment_spreads: dict = {}

    def enter_selection_set(self, selection_set: SelectionSetNode, *_args: Any) -> None:
        conflicts = find_conflicts_within_selection_set(
            self.context,
            self.cached_fields_and_fragment_spreads,
            self.compared_fields_and_fragment_pairs,
            self.compared_fragment_pairs,
            self.context.get_parent_type(),
            selection_set,
        )
        for (reason_name, reason), fields1, fields2 in conflicts:
            reason_msg = reason_message(reason)
            self.report_error(
                GraphQLError(
                    f"Fields '{reason_name}' conflict because {reason_msg}."
                    " Use different aliases on the fields to fetch both"
                    " if this was intentional.",
                    fields1 + fields2,
                )
            )


Conflict: TypeAlias = tuple["ConflictReason", list[FieldNode], list[FieldNode]]
# Field name and reason.
ConflictReason: TypeAlias = tuple[str, "ConflictReasonMessage"]
# Reason is a string, or a nested list of conflicts.
ConflictReasonMessage: TypeAlias = str | list[ConflictReason]
# Tuple defining a field node in a context.
NodeAndDef: TypeAlias = tuple[GraphQLCompositeType, FieldNode, GraphQLField | None]
# Dictionary of lists of those.
NodeAndDefCollection: TypeAlias = dict[str, list[NodeAndDef]]
# A mapping of fragment variable names to their value nodes.
VarMap: TypeAlias = "dict[str, ValueNode] | None"


class FragmentSpread(NamedTuple):
    """A fragment spread with its conflict key and fragment variable map."""

    key: str
    node: FragmentSpreadNode
    var_map: dict[str, ValueNode] | None


# Algorithm:
#
# Conflicts occur when two fields exist in a query which will produce the same
# response name, but represent differing values, thus creating a conflict.
# The algorithm below finds all conflicts via making a series of comparisons
# between fields. In order to compare as few fields as possible, this makes
# a series of comparisons "within" sets of fields and "between" sets of fields.
#
# Given any selection set, a collection produces both a set of fields by
# also including all inline fragments, as well as a list of fragments
# referenced by fragment spreads.
#
# A) Each selection set represented in the document first compares "within" its
# collected set of fields, finding any conflicts between every pair of
# overlapping fields.
# Note: This is the *only time* that the fields "within" a set are compared
# to each other. After this only fields "between" sets are compared.
#
# B) Also, if any fragment is referenced in a selection set, then a
# comparison is made "between" the original set of fields and the
# referenced fragment.
#
# C) Also, if multiple fragments are referenced, then comparisons
# are made "between" each referenced fragment.
#
# D) When comparing "between" a set of fields and a referenced fragment, first
# a comparison is made between each field in the original set of fields and
# each field in the referenced set of fields.
#
# E) Also, if any fragment is referenced in the referenced selection set,
# then a comparison is made "between" the original set of fields and the
# referenced fragment (recursively referring to step D).
#
# F) When comparing "between" two fragments, first a comparison is made between
# each field in the first referenced set of fields and each field in the the
# second referenced set of fields.
#
# G) Also, any fragments referenced by the first must be compared to the
# second, and any fragments referenced by the second must be compared to the
# first (recursively referring to step F).
#
# H) When comparing two fields, if both have selection sets, then a comparison
# is made "between" both selection sets, first comparing the set of fields in
# the first selection set with the set of fields in the second.
#
# I) Also, if any fragment is referenced in either selection set, then a
# comparison is made "between" the other set of fields and the
# referenced fragment.
#
# J) Also, if two fragments are referenced in both selection sets, then a
# comparison is made "between" the two fragments.


def find_conflicts_within_selection_set(
    context: ValidationContext,
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    parent_type: GraphQLNamedType | None,
    selection_set: SelectionSetNode,
) -> list[Conflict]:
    """Find conflicts within selection set.

    Find all conflicts found "within" a selection set, including those found via
    spreading in fragments.

    Called when visiting each SelectionSet in the GraphQL Document.
    """
    conflicts: list[Conflict] = []

    field_map, fragment_spreads = get_fields_and_fragment_spreads(
        context, cached_fields_and_fragment_spreads, parent_type, selection_set, None
    )

    # (A) Find all conflicts "within" the fields of this selection set.
    # Note: this is the *only place* `collect_conflicts_within` is called.
    collect_conflicts_within(
        context,
        conflicts,
        cached_fields_and_fragment_spreads,
        compared_fields_and_fragment_pairs,
        compared_fragment_pairs,
        field_map,
    )

    if fragment_spreads:
        # (B) Then collect conflicts between these fields and those represented by each
        # spread found.
        for i, fragment_spread in enumerate(fragment_spreads):
            collect_conflicts_between_fields_and_fragment(
                context,
                conflicts,
                cached_fields_and_fragment_spreads,
                compared_fields_and_fragment_pairs,
                compared_fragment_pairs,
                False,
                field_map,
                fragment_spread,
            )
            # (C) Then compare this fragment with all other fragments found in this
            # selection set to collect conflicts within fragments spread together.
            # This compares each item in the list of fragment spreads to every other
            # item in that same list (except for itself).
            for other_fragment_spread in fragment_spreads[i + 1 :]:
                collect_conflicts_between_fragments(
                    context,
                    conflicts,
                    cached_fields_and_fragment_spreads,
                    compared_fields_and_fragment_pairs,
                    compared_fragment_pairs,
                    False,
                    fragment_spread,
                    other_fragment_spread,
                )

    return conflicts


def collect_conflicts_between_fields_and_fragment(
    context: ValidationContext,
    conflicts: list[Conflict],
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    are_mutually_exclusive: bool,
    field_map: NodeAndDefCollection,
    fragment_spread: FragmentSpread,
) -> None:
    """Collect conflicts between fields and fragment.

    Collect all conflicts found between a set of fields and a fragment reference
    including via spreading in any nested fragments.
    """
    fragment_key = fragment_spread.key

    # Memoize so the fields and fragments are not compared for conflicts more
    # than once.
    if compared_fields_and_fragment_pairs.has(
        field_map, fragment_key, are_mutually_exclusive
    ):
        return
    compared_fields_and_fragment_pairs.add(
        field_map, fragment_key, are_mutually_exclusive
    )

    fragment = context.get_fragment(fragment_spread.node.name.value)
    if not fragment:
        return

    field_map2, referenced_fragment_spreads = (
        get_referenced_fields_and_fragment_spreads(
            context,
            cached_fields_and_fragment_spreads,
            fragment,
            fragment_spread.var_map,
        )
    )

    # Do not compare a fragment's fieldMap to itself.
    if field_map is field_map2:
        return

    # (D) First collect any conflicts between the provided collection of fields and the
    # collection of fields represented by the given fragment.
    collect_conflicts_between(
        context,
        conflicts,
        cached_fields_and_fragment_spreads,
        compared_fields_and_fragment_pairs,
        compared_fragment_pairs,
        are_mutually_exclusive,
        field_map,
        None,
        field_map2,
        fragment_spread.var_map,
    )

    # (E) Then collect any conflicts between the provided collection of fields and any
    # fragment spreads found in the given fragment.
    for referenced_fragment_spread in referenced_fragment_spreads:
        collect_conflicts_between_fields_and_fragment(
            context,
            conflicts,
            cached_fields_and_fragment_spreads,
            compared_fields_and_fragment_pairs,
            compared_fragment_pairs,
            are_mutually_exclusive,
            field_map,
            referenced_fragment_spread,
        )


def collect_conflicts_between_fragments(
    context: ValidationContext,
    conflicts: list[Conflict],
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    are_mutually_exclusive: bool,
    fragment_spread1: FragmentSpread,
    fragment_spread2: FragmentSpread,
) -> None:
    """Collect conflicts between fragments.

    Collect all conflicts found between two fragments, including via spreading in any
    nested fragments.
    """
    # No need to compare a fragment to itself.
    if fragment_spread1.key == fragment_spread2.key:
        return

    if fragment_spread1.node.name.value == fragment_spread2.node.name.value and (
        not same_arguments(
            fragment_spread1.node.arguments,
            fragment_spread1.var_map,
            fragment_spread2.node.arguments,
            fragment_spread2.var_map,
        )
    ):
        context.report_error(
            GraphQLError(
                f"Spreads '{fragment_spread1.node.name.value}' conflict because"
                f" {fragment_spread1.key} and {fragment_spread2.key}"
                " have different fragment arguments.",
                [fragment_spread1.node, fragment_spread2.node],
            )
        )
        return

    # Memoize so two fragments are not compared for conflicts more than once.
    if compared_fragment_pairs.has(
        fragment_spread1.key, fragment_spread2.key, are_mutually_exclusive
    ):
        return
    compared_fragment_pairs.add(
        fragment_spread1.key, fragment_spread2.key, are_mutually_exclusive
    )

    fragment1 = context.get_fragment(fragment_spread1.node.name.value)
    fragment2 = context.get_fragment(fragment_spread2.node.name.value)
    if not fragment1 or not fragment2:
        return

    field_map1, referenced_fragment_spreads1 = (
        get_referenced_fields_and_fragment_spreads(
            context,
            cached_fields_and_fragment_spreads,
            fragment1,
            fragment_spread1.var_map,
        )
    )

    field_map2, referenced_fragment_spreads2 = (
        get_referenced_fields_and_fragment_spreads(
            context,
            cached_fields_and_fragment_spreads,
            fragment2,
            fragment_spread2.var_map,
        )
    )

    # (F) First, collect all conflicts between these two collections of fields
    # (not including any nested fragments)
    collect_conflicts_between(
        context,
        conflicts,
        cached_fields_and_fragment_spreads,
        compared_fields_and_fragment_pairs,
        compared_fragment_pairs,
        are_mutually_exclusive,
        field_map1,
        fragment_spread1.var_map,
        field_map2,
        fragment_spread2.var_map,
    )

    # (G) Then collect conflicts between the first fragment and any nested fragments
    # spread in the second fragment.
    for referenced_fragment_spread2 in referenced_fragment_spreads2:
        collect_conflicts_between_fragments(
            context,
            conflicts,
            cached_fields_and_fragment_spreads,
            compared_fields_and_fragment_pairs,
            compared_fragment_pairs,
            are_mutually_exclusive,
            fragment_spread1,
            referenced_fragment_spread2,
        )

    # (G) Then collect conflicts between the second fragment and any nested fragments
    # spread in the first fragment.
    for referenced_fragment_spread1 in referenced_fragment_spreads1:
        collect_conflicts_between_fragments(
            context,
            conflicts,
            cached_fields_and_fragment_spreads,
            compared_fields_and_fragment_pairs,
            compared_fragment_pairs,
            are_mutually_exclusive,
            referenced_fragment_spread1,
            fragment_spread2,
        )


def find_conflicts_between_sub_selection_sets(
    context: ValidationContext,
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    are_mutually_exclusive: bool,
    parent_type1: GraphQLNamedType | None,
    selection_set1: SelectionSetNode,
    var_map1: VarMap,
    parent_type2: GraphQLNamedType | None,
    selection_set2: SelectionSetNode,
    var_map2: VarMap,
) -> list[Conflict]:
    """Find conflicts between sub selection sets.

    Find all conflicts found between two selection sets, including those found via
    spreading in fragments. Called when determining if conflicts exist between the
    sub-fields of two overlapping fields.
    """
    conflicts: list[Conflict] = []

    field_map1, fragment_spreads1 = get_fields_and_fragment_spreads(
        context,
        cached_fields_and_fragment_spreads,
        parent_type1,
        selection_set1,
        var_map1,
    )
    field_map2, fragment_spreads2 = get_fields_and_fragment_spreads(
        context,
        cached_fields_and_fragment_spreads,
        parent_type2,
        selection_set2,
        var_map2,
    )

    # (H) First, collect all conflicts between these two collections of field.
    collect_conflicts_between(
        context,
        conflicts,
        cached_fields_and_fragment_spreads,
        compared_fields_and_fragment_pairs,
        compared_fragment_pairs,
        are_mutually_exclusive,
        field_map1,
        var_map1,
        field_map2,
        var_map2,
    )

    # (I) Then collect conflicts between the first collection of fields and those
    # referenced by each fragment spread associated with the second.
    if fragment_spreads2:
        for fragment_spread2 in fragment_spreads2:
            collect_conflicts_between_fields_and_fragment(
                context,
                conflicts,
                cached_fields_and_fragment_spreads,
                compared_fields_and_fragment_pairs,
                compared_fragment_pairs,
                are_mutually_exclusive,
                field_map1,
                fragment_spread2,
            )

    # (I) Then collect conflicts between the second collection of fields and those
    # referenced by each fragment spread associated with the first.
    if fragment_spreads1:
        for fragment_spread1 in fragment_spreads1:
            collect_conflicts_between_fields_and_fragment(
                context,
                conflicts,
                cached_fields_and_fragment_spreads,
                compared_fields_and_fragment_pairs,
                compared_fragment_pairs,
                are_mutually_exclusive,
                field_map2,
                fragment_spread1,
            )

    # (J) Also collect conflicts between any fragment spreads by the first and fragment
    # spreads by the second. This compares each item in the first set of spreads to each
    # item in the second set of spreads.
    for fragment_spread1 in fragment_spreads1:
        for fragment_spread2 in fragment_spreads2:
            collect_conflicts_between_fragments(
                context,
                conflicts,
                cached_fields_and_fragment_spreads,
                compared_fields_and_fragment_pairs,
                compared_fragment_pairs,
                are_mutually_exclusive,
                fragment_spread1,
                fragment_spread2,
            )

    return conflicts


def collect_conflicts_within(
    context: ValidationContext,
    conflicts: list[Conflict],
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    field_map: NodeAndDefCollection,
) -> None:
    """Collect all Conflicts "within" one collection of fields."""
    # A field map is a keyed collection, where each key represents a response name and
    # the value at that key is a list of all fields which provide that response name.
    # For every response name, if there are multiple fields, they must be compared to
    # find a potential conflict.
    for response_name, fields in field_map.items():
        # This compares every field in the list to every other field in this list
        # (except to itself). If the list only has one item, nothing needs to be
        # compared.
        if len(fields) > 1:
            for i, field in enumerate(fields):
                for other_field in fields[i + 1 :]:
                    conflict = find_conflict(
                        context,
                        cached_fields_and_fragment_spreads,
                        compared_fields_and_fragment_pairs,
                        compared_fragment_pairs,
                        # within one collection is never mutually exclusive
                        False,
                        response_name,
                        field,
                        None,
                        other_field,
                        None,
                    )
                    if conflict:
                        conflicts.append(conflict)


def collect_conflicts_between(
    context: ValidationContext,
    conflicts: list[Conflict],
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    parent_fields_are_mutually_exclusive: bool,
    field_map1: NodeAndDefCollection,
    var_map1: VarMap,
    field_map2: NodeAndDefCollection,
    var_map2: VarMap,
) -> None:
    """Collect all Conflicts between two collections of fields.

    This is similar to, but different from the :func:`~.collect_conflicts_within`
    function above. This check assumes that :func:`~.collect_conflicts_within` has
    already been called on each provided collection of fields. This is true because
    this validator traverses each individual selection set.
    """
    # A field map is a keyed collection, where each key represents a response name and
    # the value at that key is a list of all fields which provide that response name.
    # For any response name which appears in both provided field maps, each field from
    # the first field map must be compared to every field in the second field map to
    # find potential conflicts.
    for response_name, fields1 in field_map1.items():
        fields2 = field_map2.get(response_name)
        if fields2:
            for field1 in fields1:
                for field2 in fields2:
                    conflict = find_conflict(
                        context,
                        cached_fields_and_fragment_spreads,
                        compared_fields_and_fragment_pairs,
                        compared_fragment_pairs,
                        parent_fields_are_mutually_exclusive,
                        response_name,
                        field1,
                        var_map1,
                        field2,
                        var_map2,
                    )
                    if conflict:
                        conflicts.append(conflict)


def find_conflict(
    context: ValidationContext,
    cached_fields_and_fragment_spreads: dict,
    compared_fields_and_fragment_pairs: OrderedPairSet,
    compared_fragment_pairs: PairSet,
    parent_fields_are_mutually_exclusive: bool,
    response_name: str,
    field1: NodeAndDef,
    var_map1: VarMap,
    field2: NodeAndDef,
    var_map2: VarMap,
) -> Conflict | None:
    """Find conflict.

    Determines if there is a conflict between two particular fields, including comparing
    their sub-fields.
    """
    parent_type1, node1, def1 = field1
    parent_type2, node2, def2 = field2

    # If it is known that two fields could not possibly apply at the same time, due to
    # the parent types, then it is safe to permit them to diverge in aliased field or
    # arguments used as they will not present any ambiguity by differing. It is known
    # that two parent types could never overlap if they are different Object types.
    # Interface or Union types might overlap - if not in the current state of the
    # schema, then perhaps in some future version, thus may not safely diverge.
    are_mutually_exclusive = parent_fields_are_mutually_exclusive or (
        parent_type1 != parent_type2
        and is_object_type(parent_type1)
        and is_object_type(parent_type2)
    )

    # The return type for each field.
    type1 = cast("GraphQLOutputType | None", def1 and def1.type)
    type2 = cast("GraphQLOutputType | None", def2 and def2.type)

    if not are_mutually_exclusive:
        # Two aliases must refer to the same field.
        name1 = node1.name.value
        name2 = node2.name.value
        if name1 != name2:
            return (
                (response_name, f"'{name1}' and '{name2}' are different fields"),
                [node1],
                [node2],
            )

        # Two field calls must have the same arguments.
        if not same_arguments(node1.arguments, var_map1, node2.arguments, var_map2):
            return (response_name, "they have differing arguments"), [node1], [node2]

    directives1 = node1.directives
    directives2 = node2.directives
    if not same_streams(directives1, directives2):
        return (
            (response_name, "they have differing stream directives"),
            [node1],
            [node2],
        )

    if type1 and type2 and do_types_conflict(type1, type2):
        return (
            (response_name, f"they return conflicting types '{type1}' and '{type2}'"),
            [node1],
            [node2],
        )

    # Collect and compare sub-fields. Use the same "visited fragment spreads" list for
    # both collections so fields in a fragment reference are never compared to
    # themselves.
    selection_set1 = node1.selection_set
    selection_set2 = node2.selection_set
    if selection_set1 and selection_set2:
        conflicts = find_conflicts_between_sub_selection_sets(
            context,
            cached_fields_and_fragment_spreads,
            compared_fields_and_fragment_pairs,
            compared_fragment_pairs,
            are_mutually_exclusive,
            get_named_type(type1),
            selection_set1,
            var_map1,
            get_named_type(type2),
            selection_set2,
            var_map2,
        )
        return subfield_conflicts(conflicts, response_name, node1, node2)

    return None  # no conflict


def same_arguments(
    args1: Sequence[ArgumentNode | FragmentArgumentNode] | None,
    var_map1: VarMap,
    args2: Sequence[ArgumentNode | FragmentArgumentNode] | None,
    var_map2: VarMap,
) -> bool:
    if not args1:
        return not args2

    if not args2:
        return False

    if len(args1) != len(args2):
        return False

    values2 = {
        arg.name.value: (
            arg.value
            if var_map2 is None
            else replace_fragment_variables(arg.value, var_map2)
        )
        for arg in args2
    }

    for arg1 in args1:
        value1 = arg1.value
        if var_map1:
            value1 = replace_fragment_variables(value1, var_map1)
        value2 = values2.get(arg1.name.value)
        if value2 is None or stringify_value(value1) != stringify_value(value2):
            return False

    return True


def replace_fragment_variables(
    value_node: ValueNode, var_map: dict[str, ValueNode]
) -> ValueNode:
    """Replace fragment variable references in a value node using the variable map."""
    if isinstance(value_node, VariableNode):
        return var_map.get(value_node.name.value, value_node)
    if isinstance(value_node, ListValueNode):
        return ListValueNode(
            values=tuple(
                replace_fragment_variables(node, var_map) for node in value_node.values
            ),
            loc=value_node.loc,
        )
    if isinstance(value_node, ObjectValueNode):
        return ObjectValueNode(
            fields=tuple(
                ObjectFieldNode(
                    name=field.name,
                    value=replace_fragment_variables(field.value, var_map),
                    loc=field.loc,
                )
                for field in value_node.fields
            ),
            loc=value_node.loc,
        )
    return value_node


def stringify_value(value: ValueNode) -> str:
    return print_ast(sort_value_node(value))


def get_stream_directive(
    directives: Sequence[DirectiveNode] | None,
) -> DirectiveNode | None:
    for directive in directives or ():
        if directive.name.value == "stream":
            return directive
    return None


def same_streams(
    directives1: Sequence[DirectiveNode] | None,
    directives2: Sequence[DirectiveNode] | None,
) -> bool:
    stream1 = get_stream_directive(directives1)
    stream2 = get_stream_directive(directives2)
    if not stream1 and not stream2:
        # both fields do not have streams
        return True
    if stream1 and stream2:
        # check if both fields have equivalent streams
        return same_arguments(stream1.arguments, None, stream2.arguments, None)
    # fields have a mix of stream and no stream
    return False


def do_types_conflict(type1: GraphQLOutputType, type2: GraphQLOutputType) -> bool:
    """Check whether two types conflict

    Two types conflict if both types could not apply to a value simultaneously.
    Composite types are ignored as their individual field types will be compared later
    recursively. However List and Non-Null types must match.
    """
    if is_list_type(type1):
        return (
            do_types_conflict(type1.of_type, type2.of_type)
            if is_list_type(type2)
            else True
        )
    if is_list_type(type2):
        return True
    if is_non_null_type(type1):
        return (
            do_types_conflict(type1.of_type, type2.of_type)
            if is_non_null_type(type2)
            else True
        )
    if is_non_null_type(type2):
        return True
    if is_leaf_type(type1) or is_leaf_type(type2):
        return type1 is not type2
    return False


def get_fields_and_fragment_spreads(
    context: ValidationContext,
    cached_fields_and_fragment_spreads: dict,
    parent_type: GraphQLNamedType | None,
    selection_set: SelectionSetNode,
    var_map: VarMap,
) -> tuple[NodeAndDefCollection, list[FragmentSpread]]:
    """Get fields and referenced fragment spreads

    Given a selection set, return the collection of fields (a mapping of response name
    to field nodes and definitions) as well as a list of fragment spreads referenced
    via fragment spreads.
    """
    cached = cached_fields_and_fragment_spreads.get(selection_set)
    if not cached:
        node_and_defs: NodeAndDefCollection = {}
        fragment_spreads: dict[str, FragmentSpread] = {}
        collect_fields_and_fragment_spreads(
            context,
            parent_type,
            selection_set,
            node_and_defs,
            fragment_spreads,
            var_map,
        )
        cached = (node_and_defs, list(fragment_spreads.values()))
        cached_fields_and_fragment_spreads[selection_set] = cached
    return cached


def get_referenced_fields_and_fragment_spreads(
    context: ValidationContext,
    cached_fields_and_fragment_spreads: dict,
    fragment: FragmentDefinitionNode,
    var_map: VarMap,
) -> tuple[NodeAndDefCollection, list[FragmentSpread]]:
    """Get referenced fields and nested fragment spreads

    Given a reference to a fragment, return the represented collection of fields as well
    as a list of nested fragment spreads referenced via fragment spreads.
    """
    # Short-circuit building a type from the node if possible.
    cached = cached_fields_and_fragment_spreads.get(fragment.selection_set)
    if cached:
        return cached

    fragment_type = type_from_ast(context.schema, fragment.type_condition)
    return get_fields_and_fragment_spreads(
        context,
        cached_fields_and_fragment_spreads,
        fragment_type,
        fragment.selection_set,
        var_map,
    )


def collect_fields_and_fragment_spreads(
    context: ValidationContext,
    parent_type: GraphQLNamedType | None,
    selection_set: SelectionSetNode,
    node_and_defs: NodeAndDefCollection,
    fragment_spreads: dict[str, FragmentSpread],
    var_map: VarMap,
) -> None:
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            field_name = selection.name.value
            field_def = (
                parent_type.fields.get(field_name)
                if is_object_type(parent_type) or is_interface_type(parent_type)
                else None
            )
            response_name = selection.alias.value if selection.alias else field_name
            if not node_and_defs.get(response_name):
                node_and_defs[response_name] = []
            node_and_defs[response_name].append(
                cast("NodeAndDef", (parent_type, selection, field_def))
            )
        elif isinstance(selection, FragmentSpreadNode):
            fragment_spread = get_fragment_spread(context, selection, var_map)
            fragment_spreads[fragment_spread.key] = fragment_spread
        elif isinstance(selection, InlineFragmentNode):  # pragma: no branch
            type_condition = selection.type_condition
            inline_fragment_type = (
                type_from_ast(context.schema, type_condition)
                if type_condition
                else parent_type
            )
            collect_fields_and_fragment_spreads(
                context,
                inline_fragment_type,
                selection.selection_set,
                node_and_defs,
                fragment_spreads,
                var_map,
            )


def get_fragment_spread(
    context: ValidationContext,
    fragment_spread_node: FragmentSpreadNode,
    var_map: VarMap,
) -> FragmentSpread:
    """Build a fragment spread with a conflict key and resolved fragment variables."""
    key = fragment_spread_node.name.value
    new_var_map: dict[str, ValueNode] = {}
    fragment_signature = context.get_fragment_signature_by_name()(
        fragment_spread_node.name.value
    )
    if fragment_signature is not None:
        arg_map: dict[str, ValueNode] = {}
        if fragment_spread_node.arguments:
            for arg in fragment_spread_node.arguments:
                arg_map[arg.name.value] = arg.value
        key += "("
        for var_name, variable in fragment_signature.variable_definitions.items():
            value = arg_map.get(var_name)
            if value:
                key += var_name + ": " + print_ast(sort_value_node(value))
                new_var_map[var_name] = (
                    replace_fragment_variables(value, var_map) if var_map else value
                )
            elif variable.default_value is not None:
                new_var_map[var_name] = variable.default_value
        key += ")"
    return FragmentSpread(
        key=key,
        node=fragment_spread_node,
        var_map=new_var_map or None,
    )


def subfield_conflicts(
    conflicts: list[Conflict], response_name: str, node1: FieldNode, node2: FieldNode
) -> Conflict | None:
    """Check whether there are conflicts between sub-fields.

    Given a series of Conflicts which occurred between two sub-fields, generate a single
    Conflict.
    """
    if conflicts:
        return (
            (response_name, [conflict[0] for conflict in conflicts]),
            list(chain([node1], *[conflict[1] for conflict in conflicts])),
            list(chain([node2], *[conflict[2] for conflict in conflicts])),
        )
    return None  # no conflict


class OrderedPairSet:
    """Ordered pair set

    A way to keep track of pairs of things where the ordering of the pair matters.

    Provides a third argument for has/add to allow flagging the pair as weakly or
    strongly present within the collection.

    The first element is matched by object identity (its ``id``), since field maps
    are unhashable mappings that are kept alive for the duration of the validation.
    """

    __slots__ = ("_data",)

    _data: dict[int, dict[str, bool]]

    def __init__(self) -> None:
        self._data = {}

    def has(self, a: NodeAndDefCollection, b: str, weakly_present: bool) -> bool:
        map_ = self._data.get(id(a))
        if map_ is None:
            return False
        result = map_.get(b)
        if result is None:
            return False

        return True if weakly_present else weakly_present == result

    def add(self, a: NodeAndDefCollection, b: str, weakly_present: bool) -> None:
        map_ = self._data.get(id(a))
        if map_ is None:
            self._data[id(a)] = {b: weakly_present}
        else:
            map_[b] = weakly_present


class PairSet:
    """Pair set

    A way to keep track of pairs of things when the ordering of the pair doesn't matter.
    """

    __slots__ = ("_data",)

    _data: dict[str, dict[str, bool]]

    def __init__(self) -> None:
        self._data = {}

    def has(self, a: str, b: str, are_mutually_exclusive: bool) -> bool:
        key1, key2 = (a, b) if a < b else (b, a)

        map_ = self._data.get(key1)
        if map_ is None:
            return False
        result = map_.get(key2)
        if result is None:
            return False

        # are_mutually_exclusive being False is a superset of being True,
        # hence if we want to know if this PairSet "has" these two with no exclusivity,
        # we have to ensure it was added as such.
        return True if are_mutually_exclusive else are_mutually_exclusive == result

    def add(self, a: str, b: str, are_mutually_exclusive: bool) -> None:
        key1, key2 = (a, b) if a < b else (b, a)

        map_ = self._data.get(key1)
        if map_ is None:
            self._data[key1] = {key2: are_mutually_exclusive}
        else:
            map_[key2] = are_mutually_exclusive
