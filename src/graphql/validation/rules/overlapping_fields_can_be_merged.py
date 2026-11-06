"""Overlapping fields can be merged rule"""

import json
import warnings
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, cast

from ...error import GraphQLError
from ...language import (
    ArgumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    ListValueNode,
    ObjectValueNode,
    SelectionSetNode,
    StringValueNode,
    ValueNode,
    VariableNode,
)
from ...type import (
    GraphQLField,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLOutputType,
    get_named_type,
    is_interface_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
)
from ...utilities import type_from_ast
from . import ValidationContext, ValidationRule

__all__ = [
    "MAX_COMPLEXITY_BUDGET",
    "MAX_FIELD_COMPARISONS",
    "OverlappingFieldsCanBeMergedRule",
]

# Meter work that can grow through repeated comparisons. Once the budget is exhausted,
# the whole validation is aborted with an error. Collecting a selection set's fields is
# cached and is not charged. The default is high enough that any realistic query stays
# far below it; it can be raised or lowered by assigning to this module attribute, which
# is read when the validation of the rule starts.
MAX_COMPLEXITY_BUDGET = 500_000

# Deprecated, use MAX_COMPLEXITY_BUDGET instead. If this is changed, the budget is two
# times its value, because a comparison of two fields costs two units of the budget.
MAX_FIELD_COMPARISONS = 250_000

# Keep diagnostic detail bounded independently of document size.
MAX_CONFLICT_DETAIL_LENGTH = 1000
MAX_CONFLICT_NODES = 20


class OverlappingFieldsCanBeMergedRule(ValidationRule):
    """Overlapping fields can be merged

    A selection set is only valid if all fields (including spreading any fragments)
    either correspond to distinct response names or can be merged without ambiguity.

    See https://spec.graphql.org/draft/#sec-Field-Selection-Merging

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import OverlappingFieldsCanBeMergedRule
    >>> sdl = 'type Query { dog: Dog } type Dog { name: String barkVolume: Int }'
    >>> schema = build_schema(sdl)
    >>> document = parse('{ dog { value: barkVolume value: name } }')
    >>> errors = validate(schema, document, [OverlappingFieldsCanBeMergedRule])
    >>> print(errors[0].message)
    Fields 'value' conflict because 'barkVolume' and 'name' are different fields.
    Use different aliases on the fields to fetch both if this was intentional.
    >>> document = parse('{ dog { barkVolume name } }')
    >>> validate(schema, document, [OverlappingFieldsCanBeMergedRule])
    []
    """

    def __init__(self, context: ValidationContext):
        super().__init__(context)
        self.rule_context = RuleContext()

    def enter_selection_set(
        self, selection_set: SelectionSetNode, _key: Any, parent: Any, *_args: Any
    ) -> None:
        """Called when entering a selection set node.

        :meta private:
        """
        # Inline fragments are flattened into their enclosing response level.
        # Their fields' own selection sets are still visited independently.
        if isinstance(parent, InlineFragmentNode):
            return
        selections = selection_set.selections
        if len(selections) <= 1 and not (
            selections and isinstance(selections[0], InlineFragmentNode)
        ):
            return
        conflicts = find_conflicts_within_selection_set(
            self.context,
            self.rule_context,
            self.context.get_parent_type(),
            selection_set,
        )
        for response_name, reason, fields1, fields2 in conflicts:
            self.report_error(
                GraphQLError(
                    f"Fields '{maybe_abbreviate(response_name)}'"
                    f" conflict because {reason}."
                    " Use different aliases on the fields to fetch both"
                    " if this was intentional.",
                    fields1 + fields2,
                )
            )


class Conflict(NamedTuple):
    """A conflict with the field nodes on both sides."""

    response_name: str
    reason: str
    fields1: List[FieldNode]
    fields2: List[FieldNode]


class FieldDetails:
    """A field node and its definition in the parent-type context."""

    __slots__ = "definition", "info", "is_simple_leaf", "node", "parent_type"

    info: Optional["FieldInfo"]

    def __init__(
        self,
        parent_type: Optional[GraphQLNamedType],
        node: FieldNode,
        definition: Optional[GraphQLField],
        is_simple_leaf: bool,
    ) -> None:
        self.parent_type = parent_type
        self.node = node
        self.definition = definition
        self.info = None
        self.is_simple_leaf = is_simple_leaf


class ArgumentInfo(NamedTuple):
    """Argument nodes together with their values by name."""

    nodes: Sequence[ArgumentNode]
    values: Dict[str, ValueNode]


class FieldInfo:
    """Argument data of a field that is compared with other fields."""

    __slots__ = "arguments", "comparisons", "named_type", "type_string"

    def __init__(
        self, named_type: Optional[GraphQLNamedType], arguments: Optional[ArgumentInfo]
    ) -> None:
        self.named_type = named_type
        # An empty reason means the field names and arguments match.
        self.comparisons: Dict[FieldInfo, str] = {}
        self.arguments = arguments
        self.type_string: Optional[str] = None


FieldDetailsList = List[FieldDetails]
GroupedFieldSet = Dict[str, FieldDetailsList]


class OverlappingFields(NamedTuple):
    """The fields of two collections that have the same response name."""

    response_name: str
    fields1: FieldDetailsList
    fields2: FieldDetailsList


class CollectFieldsResult:
    """The fields and fragment names collected from a selection set."""

    __slots__ = (
        "compared_fragments",
        "fragment_names",
        "grouped_field_set",
        "overlapping_fields",
    )

    compared_fragments: Optional[Dict[str, bool]]
    overlapping_fields: Optional[Dict["CollectFieldsResult", List[OverlappingFields]]]

    def __init__(
        self, grouped_field_set: GroupedFieldSet, fragment_names: List[str]
    ) -> None:
        self.grouped_field_set = grouped_field_set
        self.fragment_names = fragment_names
        self.compared_fragments = None
        self.overlapping_fields = None


class RuleContext:
    """The state of the rule that is shared during the validation of a document."""

    __slots__ = (
        "cached_collect_fields_results",
        "compared_fragment_pairs",
        "remaining_complexity_budget",
        "stringified_values",
    )

    def __init__(self) -> None:
        # A memoization for when two fragments are compared for conflicts. Comparisons
        # may be made many times, so memoizing this can dramatically improve the
        # performance of this validator.
        self.compared_fragment_pairs = PairSet()

        # A cache for the "field map" and list of fragment names found in any given
        # selection set.
        # Keyed by parent type and by the id of the selection set node, because AST
        # nodes are compared by value and the document keeps them alive.
        self.cached_collect_fields_results: Dict[
            Optional[GraphQLNamedType], Dict[int, CollectFieldsResult]
        ] = {}

        # The comparison keys of value nodes, by the id of the node, because AST nodes
        # are compared by value and the document keeps them alive.
        self.stringified_values: Dict[int, str] = {}

        self.remaining_complexity_budget = get_complexity_budget()


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
# each field in the first referenced set of fields and each field in the
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
    validation_context: ValidationContext,
    rule_context: "RuleContext",
    parent_type: Optional[GraphQLNamedType],
    selection_set: SelectionSetNode,
) -> List[Conflict]:
    """Find conflicts within selection set.

    Find all conflicts found "within" a selection set, including those found via
    spreading in fragments. Inline-fragment selection sets are included in their
    enclosing collection.
    """
    conflicts: List[Conflict] = []

    collect_fields_result = collect_fields(
        validation_context, rule_context, parent_type, selection_set
    )

    # (A) Find all conflicts "within" the fields of this selection set.
    # Note: this is the *only place* `collect_conflicts_within` is called.
    collect_conflicts_within(
        validation_context,
        conflicts,
        rule_context,
        collect_fields_result.grouped_field_set,
    )

    # Compare fragment uses only with fields or another spread.
    fragment_names = collect_fields_result.fragment_names
    if fragment_names and (
        collect_fields_result.grouped_field_set or len(fragment_names) > 1
    ):
        # (B) Then collect conflicts between these fields and those represented by each
        # spread fragment name found.
        for i, fragment_name in enumerate(fragment_names):
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                conflicts,
                rule_context,
                False,
                collect_fields_result,
                fragment_name,
            )
            # (C) Then compare this fragment with all other fragments found in this
            # selection set to collect conflicts within fragments spread together.
            # This compares each item in the list of fragment names to every other
            # item in that same list (except for itself).
            for other_fragment_name in fragment_names[i + 1 :]:
                collect_conflicts_between_fragments(
                    validation_context,
                    conflicts,
                    rule_context,
                    False,
                    fragment_name,
                    other_fragment_name,
                )

    return conflicts


def collect_conflicts_between_fields_and_fragment(
    validation_context: ValidationContext,
    conflicts: List[Conflict],
    rule_context: "RuleContext",
    are_mutually_exclusive: bool,
    collect_fields_result: CollectFieldsResult,
    fragment_name: str,
) -> None:
    """Collect conflicts between fields and fragment.

    Collect all conflicts found between a set of fields and a fragment reference
    including via spreading in any nested fragments.
    """
    # Callers can enumerate more field-map/fragment pairs than document nodes.
    # Count attempts even when an empty collection or the pair cache skips them.
    spend_complexity_budget(rule_context, 1)

    if not collect_fields_result.grouped_field_set:
        return

    compared_fragments = collect_fields_result.compared_fragments
    if compared_fragments is None:
        compared_fragments = collect_fields_result.compared_fragments = {}
    # Memoize so the fields and fragments are not compared for conflicts more
    # than once.
    compared = compared_fragments.get(fragment_name)
    # Only a non-exclusive comparison can be reused for overlapping parents.
    if compared is False or (are_mutually_exclusive and compared is True):
        return
    compared_fragments[fragment_name] = are_mutually_exclusive

    fragment = validation_context.get_fragment(fragment_name)
    if not fragment:
        return None

    collect_fields_result2 = collect_fragment_fields(
        validation_context, rule_context, fragment
    )

    # Do not compare a fragment's collect_fields_result to itself.
    if collect_fields_result is collect_fields_result2:
        return

    # (D) First collect any conflicts between the provided collection of fields and the
    # collection of fields represented by the given fragment.
    collect_conflicts_between(
        validation_context,
        conflicts,
        rule_context,
        are_mutually_exclusive,
        collect_fields_result,
        collect_fields_result2,
    )

    # (E) Then collect any conflicts between the provided collection of fields and any
    # fragment names found in the given fragment.
    for referenced_fragment_name in collect_fields_result2.fragment_names:
        collect_conflicts_between_fields_and_fragment(
            validation_context,
            conflicts,
            rule_context,
            are_mutually_exclusive,
            collect_fields_result,
            referenced_fragment_name,
        )


def collect_conflicts_between_fragments(
    validation_context: ValidationContext,
    conflicts: List[Conflict],
    rule_context: "RuleContext",
    are_mutually_exclusive: bool,
    fragment_name1: str,
    fragment_name2: str,
) -> None:
    """Collect conflicts between fragments.

    Collect all conflicts found between two fragments, including via spreading in any
    nested fragments.
    """
    # Count attempted fragment pairs, including identity and cache hits.
    spend_complexity_budget(rule_context, 2)

    compared_fragment_pairs = rule_context.compared_fragment_pairs
    # No need to compare a fragment to itself.
    if fragment_name1 == fragment_name2:
        return

    # Memoize so two fragments are not compared for conflicts more than once.
    if compared_fragment_pairs.has(
        fragment_name1, fragment_name2, are_mutually_exclusive
    ):
        return
    compared_fragment_pairs.add(fragment_name1, fragment_name2, are_mutually_exclusive)

    fragment1 = validation_context.get_fragment(fragment_name1)
    fragment2 = validation_context.get_fragment(fragment_name2)
    if not fragment1 or not fragment2:
        return None

    collect_fields_result1 = collect_fragment_fields(
        validation_context, rule_context, fragment1
    )
    collect_fields_result2 = collect_fragment_fields(
        validation_context, rule_context, fragment2
    )

    # (F) First, collect all conflicts between these two collections of fields
    # (not including any nested fragments)
    collect_conflicts_between(
        validation_context,
        conflicts,
        rule_context,
        are_mutually_exclusive,
        collect_fields_result1,
        collect_fields_result2,
    )

    # (G) Then collect conflicts between the first fragment and any nested fragments
    # spread in the second fragment.
    for referenced_fragment_name2 in collect_fields_result2.fragment_names:
        collect_conflicts_between_fragments(
            validation_context,
            conflicts,
            rule_context,
            are_mutually_exclusive,
            fragment_name1,
            referenced_fragment_name2,
        )

    # (G) Then collect conflicts between the second fragment and any nested fragments
    # spread in the first fragment.
    for referenced_fragment_name1 in collect_fields_result1.fragment_names:
        collect_conflicts_between_fragments(
            validation_context,
            conflicts,
            rule_context,
            are_mutually_exclusive,
            referenced_fragment_name1,
            fragment_name2,
        )


def find_conflicts_between_sub_selection_sets(
    validation_context: ValidationContext,
    rule_context: "RuleContext",
    are_mutually_exclusive: bool,
    parent_type1: Optional[GraphQLNamedType],
    selection_set1: SelectionSetNode,
    parent_type2: Optional[GraphQLNamedType],
    selection_set2: SelectionSetNode,
) -> List[Conflict]:
    """Find conflicts between sub selection sets.

    Find all conflicts found between two selection sets, including those found via
    spreading in fragments. Called when determining if conflicts exist between the
    sub-fields of two overlapping fields.
    """
    conflicts: List[Conflict] = []

    collect_fields_result1 = collect_fields(
        validation_context, rule_context, parent_type1, selection_set1
    )
    collect_fields_result2 = collect_fields(
        validation_context, rule_context, parent_type2, selection_set2
    )
    fragment_names1 = collect_fields_result1.fragment_names
    fragment_names2 = collect_fields_result2.fragment_names

    # (H) First, collect all conflicts between these two collections of field.
    collect_conflicts_between(
        validation_context,
        conflicts,
        rule_context,
        are_mutually_exclusive,
        collect_fields_result1,
        collect_fields_result2,
    )

    # (I) Then collect conflicts between the first collection of fields and those
    # referenced by each fragment name associated with the second.
    if fragment_names2:
        for fragment_name2 in fragment_names2:
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                conflicts,
                rule_context,
                are_mutually_exclusive,
                collect_fields_result1,
                fragment_name2,
            )

    # (I) Then collect conflicts between the second collection of fields and those
    # referenced by each fragment name associated with the first.
    if fragment_names1:
        for fragment_name1 in fragment_names1:
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                conflicts,
                rule_context,
                are_mutually_exclusive,
                collect_fields_result2,
                fragment_name1,
            )

    # (J) Also collect conflicts between any fragment names by the first and fragment
    # names by the second. This compares each item in the first set of names to each
    # item in the second set of names.
    for fragment_name1 in fragment_names1:
        for fragment_name2 in fragment_names2:
            collect_conflicts_between_fragments(
                validation_context,
                conflicts,
                rule_context,
                are_mutually_exclusive,
                fragment_name1,
                fragment_name2,
            )

    return conflicts


def collect_conflicts_within(
    validation_context: ValidationContext,
    conflicts: List[Conflict],
    rule_context: "RuleContext",
    grouped_field_set: GroupedFieldSet,
) -> None:
    """Collect all Conflicts "within" one collection of fields."""
    # A field map is a keyed collection, where each key represents a response name and
    # the value at that key is a list of all fields which provide that response name.
    # For every response name, if there are multiple fields, they must be compared to
    # find a potential conflict.
    for response_name, field_details_list in grouped_field_set.items():
        # This compares every field in the list to every other field in this list
        # (except to itself). If the list only has one item, nothing needs to be
        # compared.
        if len(field_details_list) > 1:
            for i, field_details in enumerate(field_details_list):
                for other_field_details in field_details_list[i + 1 :]:
                    conflict = find_conflict(
                        validation_context,
                        rule_context,
                        # within one collection is never mutually exclusive
                        False,
                        response_name,
                        field_details,
                        other_field_details,
                    )
                    if conflict:
                        conflicts.append(conflict)


def collect_conflicts_between(
    validation_context: ValidationContext,
    conflicts: List[Conflict],
    rule_context: "RuleContext",
    parent_fields_are_mutually_exclusive: bool,
    collect_fields_result1: CollectFieldsResult,
    collect_fields_result2: CollectFieldsResult,
) -> None:
    """Collect all Conflicts between two collections of fields.

    This is similar to, but different from the :func:`~.collect_conflicts_within`
    function above. This check assumes that :func:`~.collect_conflicts_within` has
    already been called on each provided collection of fields. This is true because
    this validator traverses each individual selection set.
    """
    if (
        not collect_fields_result1.grouped_field_set
        or not collect_fields_result2.grouped_field_set
    ):
        return

    # A field map is a keyed collection, where each key represents a response name and
    # the value at that key is a list of all fields which provide that response name.
    # For any response name which appears in both provided field maps, each field from
    # the first field map must be compared to every field in the second field map to
    # find potential conflicts.
    for response_name, fields1, fields2 in get_overlapping_fields(
        rule_context, collect_fields_result1, collect_fields_result2
    ):
        for field_details1 in fields1:
            for field_details2 in fields2:
                conflict = find_conflict(
                    validation_context,
                    rule_context,
                    parent_fields_are_mutually_exclusive,
                    response_name,
                    field_details1,
                    field_details2,
                )
                if conflict:
                    conflicts.append(conflict)


def get_overlapping_fields(
    rule_context: "RuleContext",
    collect_fields_result1: CollectFieldsResult,
    collect_fields_result2: CollectFieldsResult,
) -> List[OverlappingFields]:
    """Get the fields of two collections that have the same response name.

    Reuse matching response groups when these collections are compared again.
    """
    by_collect_fields_result = collect_fields_result1.overlapping_fields
    if by_collect_fields_result is None:
        by_collect_fields_result = collect_fields_result1.overlapping_fields = {}
    cached = by_collect_fields_result.get(collect_fields_result2)
    if cached is not None:
        return cached
    overlapping_fields: List[OverlappingFields] = []
    grouped_field_set2 = collect_fields_result2.grouped_field_set
    for response_name, fields1 in collect_fields_result1.grouped_field_set.items():
        # A field map can participate in many distinct comparisons.
        spend_complexity_budget(rule_context, 1)
        fields2 = grouped_field_set2.get(response_name)
        if fields2:
            overlapping_fields.append(
                OverlappingFields(response_name, fields1, fields2)
            )
    by_collect_fields_result[collect_fields_result2] = overlapping_fields
    return overlapping_fields


def find_conflict(
    validation_context: ValidationContext,
    rule_context: "RuleContext",
    parent_fields_are_mutually_exclusive: bool,
    response_name: str,
    field_details1: FieldDetails,
    field_details2: FieldDetails,
) -> Optional[Conflict]:
    """Find conflict.

    Determines if there is a conflict between two particular fields, including comparing
    their sub-fields.
    """
    parent_type1 = field_details1.parent_type
    node1 = field_details1.node
    def1 = field_details1.definition
    parent_type2 = field_details2.parent_type
    node2 = field_details2.node
    def2 = field_details2.definition

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
    type1 = cast(Optional[GraphQLOutputType], def1 and def1.type)
    type2 = cast(Optional[GraphQLOutputType], def2 and def2.type)

    # Count attempted field pairs, including pairs skipped by type exclusivity.
    spend_complexity_budget(rule_context, 2)
    if (
        field_details1.is_simple_leaf
        and field_details2.is_simple_leaf
        and type1 is type2
        and node1.name.value == node2.name.value
    ):
        return None

    if not are_mutually_exclusive:
        field_info1 = get_field_info(field_details1)
        field_info2 = get_field_info(field_details2)
        reason = field_info1.comparisons.get(field_info2)
        if reason is None:
            # Two aliases must refer to the same field with the same arguments.
            name1 = node1.name.value
            name2 = node2.name.value
            if name1 != name2:
                reason = (
                    f"'{maybe_abbreviate(name1)}' and '{maybe_abbreviate(name2)}'"
                    " are different fields"
                )
            elif same_arguments(
                rule_context, field_info1.arguments, field_info2.arguments
            ):
                reason = ""
            else:
                reason = "they have differing arguments"
            field_info1.comparisons[field_info2] = reason
        if reason:
            return Conflict(response_name, reason, [node1], [node2])

    if type1 and type2 and do_types_conflict(rule_context, type1, type2):
        field_info1 = get_field_info(field_details1)
        field_info2 = get_field_info(field_details2)
        type1_string = field_info1.type_string = field_info1.type_string or str(type1)
        type2_string = field_info2.type_string = field_info2.type_string or str(type2)
        return Conflict(
            response_name,
            f"they return conflicting types '{type1_string}' and '{type2_string}'",
            [node1],
            [node2],
        )

    # Collect and compare sub-fields. Use the same "visited fragment names" list for
    # both collections so fields in a fragment reference are never compared to
    # themselves.
    selection_set1 = node1.selection_set
    selection_set2 = node2.selection_set
    if selection_set1 and selection_set2:
        conflicts = find_conflicts_between_sub_selection_sets(
            validation_context,
            rule_context,
            are_mutually_exclusive,
            get_field_info(field_details1).named_type,
            selection_set1,
            get_field_info(field_details2).named_type,
            selection_set2,
        )
        return subfield_conflicts(conflicts, response_name, node1, node2)

    return None  # no conflict


def get_field_info(field_details: FieldDetails) -> FieldInfo:
    """Prepare argument lookups only when a field overlaps."""
    info = field_details.info
    if info is None:
        definition = field_details.definition
        info = field_details.info = FieldInfo(
            get_named_type(definition.type if definition else None),
            get_argument_info(field_details.node.arguments),
        )
    return info


def get_argument_info(args: Optional[Sequence[ArgumentNode]]) -> Optional[ArgumentInfo]:
    if not args:
        return None
    return ArgumentInfo(args, {arg.name.value: arg.value for arg in args})


def same_arguments(
    rule_context: RuleContext,
    argument_info1: Optional[ArgumentInfo],
    argument_info2: Optional[ArgumentInfo],
) -> bool:
    if argument_info1 is None:
        return argument_info2 is None
    if argument_info2 is None or len(argument_info1.nodes) != len(argument_info2.nodes):
        return False

    values2 = argument_info2.values
    for arg1 in argument_info1.nodes:
        # A prepared argument list can participate in many field-pair comparisons.
        spend_complexity_budget(rule_context, 1)
        value2 = values2.get(arg1.name.value)
        if value2 is None or stringify_value(
            rule_context, arg1.value
        ) != stringify_value(rule_context, value2):
            return False

    return True


def stringify_value(rule_context: RuleContext, value: ValueNode) -> str:
    stringified_values = rule_context.stringified_values
    result = stringified_values.get(id(value))
    if result is None:
        result = stringified_values[id(value)] = json.dumps(
            get_value_structure(value), separators=(",", ":"), ensure_ascii=False
        )
    return result


def get_value_structure(node: ValueNode) -> List[Any]:
    """Get a structure of nested lists with object fields ordered by name."""
    if isinstance(node, VariableNode):
        return [node.kind, node.name.value]
    if isinstance(node, ObjectValueNode):
        fields = sorted(node.fields, key=lambda field: field.name.value)
        return [
            node.kind,
            [[field.name.value, get_value_structure(field.value)] for field in fields],
        ]
    if isinstance(node, ListValueNode):
        return [node.kind, [get_value_structure(value) for value in node.values]]
    if isinstance(node, StringValueNode):
        return [node.kind, node.value, node.block is True]
    return [node.kind, getattr(node, "value", None)]


def do_types_conflict(
    rule_context: "RuleContext", type1: GraphQLOutputType, type2: GraphQLOutputType
) -> bool:
    """Check whether two types conflict

    Two types conflict if both types could not apply to a value simultaneously.
    Composite types are ignored as their individual field types will be compared later
    recursively. However List and Non-Null types must match.
    """
    if type1 is type2:
        return False
    spend_complexity_budget(rule_context, 1)
    if is_list_type(type1):
        return (
            do_types_conflict(
                rule_context,
                cast(GraphQLList, type1).of_type,
                cast(GraphQLList, type2).of_type,
            )
            if is_list_type(type2)
            else True
        )
    if is_list_type(type2):
        return True
    if is_non_null_type(type1):
        return (
            do_types_conflict(
                rule_context,
                cast(GraphQLNonNull, type1).of_type,
                cast(GraphQLNonNull, type2).of_type,
            )
            if is_non_null_type(type2)
            else True
        )
    if is_non_null_type(type2):
        return True
    if is_leaf_type(type1) or is_leaf_type(type2):
        return type1 is not type2
    return False


def collect_fields(
    validation_context: ValidationContext,
    rule_context: "RuleContext",
    parent_type: Optional[GraphQLNamedType],
    selection_set: SelectionSetNode,
) -> CollectFieldsResult:
    """Get fields and referenced fragment names

    Given a selection set, return the collection of fields (a mapping of response name
    to field nodes and definitions) as well as a list of fragment names referenced via
    fragment spreads.
    """
    cached_collect_fields_results = rule_context.cached_collect_fields_results
    # A programmatically built document can share a selection-set object between
    # different parent types; their field definitions must not share a cache entry.
    by_selection_set = cached_collect_fields_results.get(parent_type)
    if by_selection_set is None:
        by_selection_set = cached_collect_fields_results[parent_type] = {}
    cached = by_selection_set.get(id(selection_set))
    if cached is None:
        grouped_field_set: GroupedFieldSet = {}
        fragment_names: Dict[str, bool] = {}
        collect_fields_impl(
            validation_context,
            parent_type,
            selection_set,
            grouped_field_set,
            fragment_names,
        )
        cached = CollectFieldsResult(grouped_field_set, list(fragment_names))
        by_selection_set[id(selection_set)] = cached
    return cached


def collect_fragment_fields(
    validation_context: ValidationContext,
    rule_context: "RuleContext",
    fragment: FragmentDefinitionNode,
) -> CollectFieldsResult:
    """Get referenced fields and nested fragment names

    Given a reference to a fragment, return the represented collection of fields as well
    as a list of nested fragment names referenced via fragment spreads.
    """
    fragment_type = type_from_ast(validation_context.schema, fragment.type_condition)
    return collect_fields(
        validation_context, rule_context, fragment_type, fragment.selection_set
    )


def collect_fields_impl(
    validation_context: ValidationContext,
    parent_type: Optional[GraphQLNamedType],
    selection_set: SelectionSetNode,
    grouped_field_set: GroupedFieldSet,
    fragment_names: Dict[str, bool],
) -> None:
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            field_name = selection.name.value
            field_def = (
                parent_type.fields.get(field_name)  # type: ignore
                if is_object_type(parent_type) or is_interface_type(parent_type)
                else None
            )
            response_name = selection.alias.value if selection.alias else field_name
            field_details_list = grouped_field_set.get(response_name)
            if not field_details_list:
                field_details_list = grouped_field_set[response_name] = []
            field_details_list.append(
                FieldDetails(
                    parent_type,
                    selection,
                    field_def,
                    not selection.arguments and not selection.selection_set,
                )
            )
        elif isinstance(selection, FragmentSpreadNode):
            fragment_names[selection.name.value] = True
        elif isinstance(selection, InlineFragmentNode):  # pragma: no cover else
            type_condition = selection.type_condition
            inline_fragment_type = (
                type_from_ast(validation_context.schema, type_condition)
                if type_condition
                else parent_type
            )
            collect_fields_impl(
                validation_context,
                inline_fragment_type,
                selection.selection_set,
                grouped_field_set,
                fragment_names,
            )


def subfield_conflicts(
    conflicts: List[Conflict], response_name: str, node1: FieldNode, node2: FieldNode
) -> Optional[Conflict]:
    """Check whether there are conflicts between sub-fields.

    Given a series of Conflicts which occurred between two sub-fields, generate a single
    Conflict.
    """
    if conflicts:
        # Abbreviate while combining child reasons, not after expanding a whole
        # tree of conflicts.
        message = ""
        for name, reason, _fields1, _fields2 in conflicts:
            message += (
                f"{' and ' if message else ''}"
                f"subfields '{maybe_abbreviate(name)}' conflict because {reason}"
            )
            if len(message) > MAX_CONFLICT_DETAIL_LENGTH:
                break
        return Conflict(
            response_name,
            maybe_abbreviate(message),
            collect_conflict_nodes(node1, [conflict.fields1 for conflict in conflicts]),
            collect_conflict_nodes(node2, [conflict.fields2 for conflict in conflicts]),
        )
    return None  # no conflict


def collect_conflict_nodes(
    node: FieldNode, conflict_fields: List[List[FieldNode]]
) -> List[FieldNode]:
    nodes = [node]
    for fields in conflict_fields:
        remaining = MAX_CONFLICT_NODES - len(nodes)
        # Locations start with the enclosing field. Take from the end so that
        # truncation favors the deeper fields involved in the conflict.
        nodes += fields[-remaining:]
        if len(nodes) == MAX_CONFLICT_NODES:
            break
    return nodes


def get_complexity_budget() -> int:
    """Get the initial complexity budget for the validation of a document."""
    if MAX_FIELD_COMPARISONS != 250_000:
        warnings.warn(
            "MAX_FIELD_COMPARISONS is deprecated, use MAX_COMPLEXITY_BUDGET instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return 2 * MAX_FIELD_COMPARISONS
    return MAX_COMPLEXITY_BUDGET


def spend_complexity_budget(rule_context: "RuleContext", cost: int) -> None:
    rule_context.remaining_complexity_budget -= cost
    if rule_context.remaining_complexity_budget < 0:
        from ..validate import ValidationAbortedError

        msg = "Validation aborted."
        raise ValidationAbortedError(msg)


def maybe_abbreviate(text: str) -> str:
    return (
        text[:MAX_CONFLICT_DETAIL_LENGTH] + "..."
        if len(text) > MAX_CONFLICT_DETAIL_LENGTH
        else text
    )


class PairSet:
    """Pair set

    A way to keep track of pairs of things when the ordering of the pair doesn't matter.
    """

    __slots__ = ("_data",)

    _data: Dict[str, Dict[str, bool]]

    def __init__(self) -> None:
        self._data = {}

    def has(self, a: str, b: str, are_mutually_exclusive: bool) -> bool:
        return self._has_ordered(a, b, are_mutually_exclusive) or self._has_ordered(
            b, a, are_mutually_exclusive
        )

    def _has_ordered(self, a: str, b: str, are_mutually_exclusive: bool) -> bool:
        map_ = self._data.get(a)
        if map_ is None:
            return False
        result = map_.get(b)
        if result is None:
            return False

        # are_mutually_exclusive being False is a superset of being True,
        # hence if we want to know if this PairSet "has" these two with no exclusivity,
        # we have to ensure it was added as such.
        return True if are_mutually_exclusive else are_mutually_exclusive == result

    def add(self, a: str, b: str, are_mutually_exclusive: bool) -> None:
        map_ = self._data.get(a)
        if map_ is None:
            self._data[a] = {b: are_mutually_exclusive}
        else:
            map_[b] = are_mutually_exclusive
