"""Overlapping fields can be merged rule"""

from __future__ import annotations

import json
import warnings
from typing import TYPE_CHECKING, Any, NamedTuple, TypeAlias, cast

from ...error import GraphQLError
from ...language import (
    ArgumentNode,
    BooleanValueNode,
    EnumValueNode,
    FieldNode,
    FloatValueNode,
    FragmentArgumentNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    IntValueNode,
    ListValueNode,
    NameNode,
    NullValueNode,
    ObjectValueNode,
    SelectionSetNode,
    StringValueNode,
    ValueNode,
    VariableNode,
    print_ast,
)
from ...pyutils import RefMap
from ...type import (
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
from . import ValidationContext, ValidationRule

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...utilities.type_info import FragmentSignature

__all__ = [
    "MAX_COMPLEXITY_BUDGET",
    "MAX_FIELD_COMPARISONS",
    "OverlappingFieldsCanBeMergedRule",
]

# Meter work that can grow through repeated comparisons and fragment scopes. Once the
# budget is exhausted, the whole validation is aborted with an error. Collecting a
# selection set's fields is shared across scopes and is not charged. The default is high
# enough that any realistic query stays far below it; it can be raised or lowered by
# assigning to this module attribute, which is read when the validation of the rule
# starts.
MAX_COMPLEXITY_BUDGET = 500_000

# Deprecated, use MAX_COMPLEXITY_BUDGET instead. If this is changed, the budget is two
# times its value, because a comparison of two fields costs two units of the budget.
MAX_FIELD_COMPARISONS = 250_000

# Keep diagnostic detail bounded independently of document size.
MAX_CONFLICT_DETAIL_LENGTH = 1000
MAX_CONFLICT_NODES = 20
MAX_FRAGMENT_ARGUMENT_SIZE = 256


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

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self.rule_context = RuleContext()
        self.fragment_scope: VariableScope | None = None

    def enter_fragment_definition(
        self, node: FragmentDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering a fragment definition node.

        :meta private:
        """
        fragment_name = node.name.value
        fragment_signature = self.context.get_fragment_signature_by_name()(
            fragment_name
        )
        self.fragment_scope = get_variable_scope(fragment_signature)

    def leave_fragment_definition(self, *_args: Any) -> None:
        """Called when leaving a fragment definition node.

        :meta private:
        """
        self.fragment_scope = None

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
        conflicts = find_conflicts_within_selection_set(
            self.context,
            self.rule_context,
            self.context.get_parent_type(),
            selection_set,
            self.fragment_scope,
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
    fields1: list[FieldNode]
    fields2: list[FieldNode]


class FieldDetails:
    """A field node and its definition in the parent-type context."""

    __slots__ = "definition", "info", "node", "parent_type"

    info: FieldInfo | None

    def __init__(
        self,
        parent_type: GraphQLNamedType | None,
        node: FieldNode,
        definition: GraphQLField | None,
    ) -> None:
        self.parent_type = parent_type
        self.node = node
        self.definition = definition
        self.info = None


class FieldInfo:
    """Argument and stream metadata of a field that is compared with other fields."""

    __slots__ = "arguments", "comparisons", "has_stream", "stream_arguments"

    def __init__(
        self,
        arguments: ArgumentInfo | None,
        has_stream: bool,
        stream_arguments: ArgumentInfo | None,
    ) -> None:
        self.comparisons: dict[FieldInfo, FieldComparison] = {}
        self.arguments = arguments
        self.has_stream = has_stream
        self.stream_arguments = stream_arguments


class FieldComparison:
    """The source comparisons of a field pair, made when they are needed first."""

    __slots__ = "arguments", "same_name", "stream_arguments"

    same_name: bool | None
    arguments: ArgumentComparison | None
    stream_arguments: ArgumentComparison | None

    def __init__(self) -> None:
        self.same_name = None
        self.arguments = None
        self.stream_arguments = None


class ArgumentComparison(NamedTuple):
    """The result of comparing the source arguments of a field pair."""

    same_structure: bool
    values_with_variables: list[ValueInfo]


FieldDetailsList: TypeAlias = list[FieldDetails]
GroupedFieldSet: TypeAlias = dict[str, FieldDetailsList]


class OverlappingFields(NamedTuple):
    """The fields of two collections that have the same response name."""

    response_name: str
    field_details_list1: FieldDetailsList
    field_details_list2: FieldDetailsList


class VariableScope:
    """The variable scope of a fragment use.

    Equivalent spreads share a scope. The signature identifies declarations;
    object identity distinguishes scopes with different fragment arguments.
    """

    __slots__ = ("signature",)

    def __init__(self, signature: FragmentSignature) -> None:
        self.signature = signature


class FragmentSpread:
    """A fragment spread with its fragment definition and variable scope."""

    __slots__ = "definition", "node", "scope"

    def __init__(
        self,
        node: FragmentSpreadNode,
        scope: VariableScope | None,
        definition: FragmentDefinitionNode | None,
    ) -> None:
        self.node = node
        self.scope = scope
        self.definition = definition


class CollectFieldsResult:
    """The fields and fragment spreads collected from a selection set."""

    __slots__ = "by_scope", "grouped_field_set", "overlapping_fields", "spreads"

    by_scope: dict[VariableScope | None, list[FragmentSpread]] | None
    overlapping_fields: dict[CollectFieldsResult, list[OverlappingFields]] | None

    def __init__(
        self,
        grouped_field_set: GroupedFieldSet,
        spreads: list[FragmentSpreadNode],
    ) -> None:
        self.grouped_field_set = grouped_field_set
        self.spreads = spreads
        self.by_scope = None
        self.overlapping_fields = None


ArgumentNodes: TypeAlias = "Sequence[ArgumentNode] | Sequence[FragmentArgumentNode]"


class ArgumentInfo(NamedTuple):
    """Argument nodes together with their values by name."""

    nodes: ArgumentNodes
    values: dict[str, ValueNode]


class FragmentSpreadInfo:
    """The prepared source of equivalent fragment spreads."""

    __slots__ = "by_scope", "signature", "values"

    def __init__(
        self, signature: FragmentSignature | None, values: list[ValueInfo]
    ) -> None:
        self.signature = signature
        self.values = values
        # Cache the resulting fragment scope by the arguments' enclosing scope.
        # A None key means no local references; a None value means the target fragment
        # declares no variables.
        self.by_scope: dict[VariableScope | None, VariableScope | None] = {}


class RuleContext:
    """The state of the rule that is shared during the validation of a document."""

    __slots__ = (
        "cached_collect_fields_results",
        "compared_fields_and_fragment_pairs",
        "compared_fragment_pairs",
        "fragment_spread_info_by_key",
        "fragment_spread_info_by_node",
        "remaining_complexity_budget",
        "value_info_by_node",
    )

    def __init__(self) -> None:
        # A memoization for when fields and a fragment or two fragments are compared
        # "between" each other for conflicts. Comparisons may be made many times, so
        # memoizing this can dramatically improve the performance of this validator.
        self.compared_fields_and_fragment_pairs: dict[
            VariableScope | None, dict[VariableScope | None, OrderedPairSet]
        ] = {}
        self.compared_fragment_pairs: dict[
            VariableScope | None, dict[VariableScope | None, PairSet]
        ] = {}

        # A cache for the "field map" and list of fragment spreads found in any given
        # selection set.
        self.cached_collect_fields_results: dict[
            GraphQLNamedType | None,
            RefMap[SelectionSetNode, CollectFieldsResult],
        ] = {}

        self.value_info_by_node: RefMap[ValueNode, ValueInfo] = RefMap()

        self.fragment_spread_info_by_node: RefMap[
            FragmentSpreadNode, FragmentSpreadInfo
        ] = RefMap()
        self.fragment_spread_info_by_key: dict[str, FragmentSpreadInfo] = {}

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
    validation_context: ValidationContext,
    rule_context: RuleContext,
    parent_type: GraphQLNamedType | None,
    selection_set: SelectionSetNode,
    scope: VariableScope | None,
) -> list[Conflict]:
    """Find conflicts within selection set.

    Find all conflicts found "within" a selection set, including those found via
    spreading in fragments. Inline-fragment selection sets are included in their
    enclosing collection.
    """
    conflicts: list[Conflict] = []

    collect_fields_result = collect_fields(
        validation_context, rule_context, parent_type, selection_set
    )

    # (A) Find all conflicts "within" the fields of this selection set.
    # Note: this is the *only place* `collect_conflicts_within` is called.
    collect_conflicts_within(
        validation_context,
        rule_context,
        conflicts,
        collect_fields_result,
        scope,
    )

    # Prepare fragment uses only for comparisons with fields or another spread.
    spreads = collect_fields_result.spreads
    if spreads and (collect_fields_result.grouped_field_set or len(spreads) > 1):
        fragment_spreads = get_fragment_spreads(
            validation_context, rule_context, collect_fields_result, scope
        )
        # (B) Then collect conflicts between these fields and those represented by each
        # spread found.
        for i, fragment_spread in enumerate(fragment_spreads):
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                rule_context,
                conflicts,
                False,
                collect_fields_result,
                scope,
                fragment_spread,
            )
            # (C) Then compare this fragment with all other fragments found in this
            # selection set to collect conflicts within fragments spread together.
            # This compares each item in the list of fragment spreads to every other
            # item in that same list (except for itself).
            for other_fragment_spread in fragment_spreads[i + 1 :]:
                collect_conflicts_between_fragments(
                    validation_context,
                    rule_context,
                    conflicts,
                    False,
                    fragment_spread,
                    other_fragment_spread,
                )

    return conflicts


def collect_conflicts_between_fields_and_fragment(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    conflicts: list[Conflict],
    are_mutually_exclusive: bool,
    collect_fields_result: CollectFieldsResult,
    scope: VariableScope | None,
    fragment_spread: FragmentSpread,
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

    # Fields and fragments can each be compared in different variable scopes.
    # Keep a separate pair history for each pair of scopes.
    fragment = fragment_spread.definition
    by_fragment_scope = rule_context.compared_fields_and_fragment_pairs.get(scope)
    if by_fragment_scope is None:
        by_fragment_scope = {}
        rule_context.compared_fields_and_fragment_pairs[scope] = by_fragment_scope
    compared_pairs = by_fragment_scope.get(fragment_spread.scope)
    if compared_pairs is None:
        compared_pairs = OrderedPairSet()
        by_fragment_scope[fragment_spread.scope] = compared_pairs

    # Memoize so the fields and fragments are not compared for conflicts more
    # than once.
    if compared_pairs.has(collect_fields_result, fragment, are_mutually_exclusive):
        return
    compared_pairs.add(collect_fields_result, fragment, are_mutually_exclusive)

    if not fragment:
        return

    collect_fields_result2 = collect_fragment_fields(
        validation_context,
        rule_context,
        fragment,
    )
    referenced_fragment_spreads = get_fragment_spreads(
        validation_context,
        rule_context,
        collect_fields_result2,
        fragment_spread.scope,
    )

    # Do not compare a selection set to itself in the same variable scope.
    if (
        collect_fields_result is collect_fields_result2
        and scope is fragment_spread.scope
    ):
        return

    # (D) First collect any conflicts between the provided collection of fields and the
    # collection of fields represented by the given fragment.
    collect_conflicts_between(
        validation_context,
        rule_context,
        conflicts,
        are_mutually_exclusive,
        collect_fields_result,
        scope,
        collect_fields_result2,
        fragment_spread.scope,
    )

    # (E) Then collect any conflicts between the provided collection of fields and any
    # fragment spreads found in the given fragment.
    for referenced_fragment_spread in referenced_fragment_spreads:
        collect_conflicts_between_fields_and_fragment(
            validation_context,
            rule_context,
            conflicts,
            are_mutually_exclusive,
            collect_fields_result,
            scope,
            referenced_fragment_spread,
        )


def collect_conflicts_between_fragments(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    conflicts: list[Conflict],
    are_mutually_exclusive: bool,
    fragment_spread1: FragmentSpread,
    fragment_spread2: FragmentSpread,
) -> None:
    """Collect conflicts between fragments.

    Collect all conflicts found between two fragments, including via spreading in any
    nested fragments.
    """
    fragment1 = fragment_spread1.definition
    fragment2 = fragment_spread2.definition
    scope1 = fragment_spread1.scope
    scope2 = fragment_spread2.scope
    # Count attempted fragment pairs, including identity and cache hits.
    spend_complexity_budget(rule_context, 2)

    # No need to compare a fragment to itself.
    if fragment1 is fragment2 and scope1 is scope2:
        return

    # Scope pairs share a comparison history indexed by fragment definitions.
    all_compared_pairs = rule_context.compared_fragment_pairs
    by_scope = all_compared_pairs.get(scope1)
    compared_fragment_pairs = None if by_scope is None else by_scope.get(scope2)
    if compared_fragment_pairs is None:
        other_by_scope = all_compared_pairs.get(scope2)
        if other_by_scope is not None:
            compared_fragment_pairs = other_by_scope.get(scope1)
    if compared_fragment_pairs is None:
        if by_scope is None:
            by_scope = all_compared_pairs[scope1] = {}
        compared_fragment_pairs = by_scope[scope2] = PairSet()

    if fragment1 is fragment2:
        if compared_fragment_pairs.has(fragment1, fragment2, False):
            return
        compared_fragment_pairs.add(fragment1, fragment2, False)
        description1 = get_fragment_spread_description(
            rule_context, fragment_spread1.node
        )
        description2 = get_fragment_spread_description(
            rule_context, fragment_spread2.node
        )
        validation_context.report_error(
            GraphQLError(
                f"Spreads '{maybe_abbreviate(fragment_spread1.node.name.value)}'"
                f" conflict because {description1} and {description2}"
                " have different fragment arguments.",
                [fragment_spread1.node, fragment_spread2.node],
            )
        )
        return

    # Memoize so two fragments are not compared for conflicts more than once.
    if compared_fragment_pairs.has(fragment1, fragment2, are_mutually_exclusive):
        return
    compared_fragment_pairs.add(fragment1, fragment2, are_mutually_exclusive)

    if not fragment1 or not fragment2:
        return

    collect_fields_result1 = collect_fragment_fields(
        validation_context,
        rule_context,
        fragment1,
    )
    referenced_fragment_spreads1 = get_fragment_spreads(
        validation_context,
        rule_context,
        collect_fields_result1,
        fragment_spread1.scope,
    )
    collect_fields_result2 = collect_fragment_fields(
        validation_context,
        rule_context,
        fragment2,
    )
    referenced_fragment_spreads2 = get_fragment_spreads(
        validation_context,
        rule_context,
        collect_fields_result2,
        fragment_spread2.scope,
    )

    # (F) First, collect all conflicts between these two collections of fields
    # (not including any nested fragments)
    collect_conflicts_between(
        validation_context,
        rule_context,
        conflicts,
        are_mutually_exclusive,
        collect_fields_result1,
        fragment_spread1.scope,
        collect_fields_result2,
        fragment_spread2.scope,
    )

    # (G) Then collect conflicts between the first fragment and any nested fragments
    # spread in the second fragment.
    for referenced_fragment_spread2 in referenced_fragment_spreads2:
        collect_conflicts_between_fragments(
            validation_context,
            rule_context,
            conflicts,
            are_mutually_exclusive,
            fragment_spread1,
            referenced_fragment_spread2,
        )

    # (G) Then collect conflicts between the second fragment and any nested fragments
    # spread in the first fragment.
    for referenced_fragment_spread1 in referenced_fragment_spreads1:
        collect_conflicts_between_fragments(
            validation_context,
            rule_context,
            conflicts,
            are_mutually_exclusive,
            referenced_fragment_spread1,
            fragment_spread2,
        )


def find_conflicts_between_sub_selection_sets(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    are_mutually_exclusive: bool,
    parent_type1: GraphQLNamedType | None,
    selection_set1: SelectionSetNode,
    scope1: VariableScope | None,
    parent_type2: GraphQLNamedType | None,
    selection_set2: SelectionSetNode,
    scope2: VariableScope | None,
) -> list[Conflict]:
    """Find conflicts between sub selection sets.

    Find all conflicts found between two selection sets, including those found via
    spreading in fragments. Called when determining if conflicts exist between the
    sub-fields of two overlapping fields.
    """
    conflicts: list[Conflict] = []

    collect_fields_result1 = collect_fields(
        validation_context,
        rule_context,
        parent_type1,
        selection_set1,
    )
    fragment_spreads1 = get_fragment_spreads(
        validation_context,
        rule_context,
        collect_fields_result1,
        scope1,
    )
    collect_fields_result2 = collect_fields(
        validation_context,
        rule_context,
        parent_type2,
        selection_set2,
    )
    fragment_spreads2 = get_fragment_spreads(
        validation_context,
        rule_context,
        collect_fields_result2,
        scope2,
    )

    # (H) First, collect all conflicts between these two collections of field.
    collect_conflicts_between(
        validation_context,
        rule_context,
        conflicts,
        are_mutually_exclusive,
        collect_fields_result1,
        scope1,
        collect_fields_result2,
        scope2,
    )

    # (I) Then collect conflicts between the first collection of fields and those
    # referenced by each fragment spread associated with the second.
    if fragment_spreads2:
        for fragment_spread2 in fragment_spreads2:
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                rule_context,
                conflicts,
                are_mutually_exclusive,
                collect_fields_result1,
                scope1,
                fragment_spread2,
            )

    # (I) Then collect conflicts between the second collection of fields and those
    # referenced by each fragment spread associated with the first.
    if fragment_spreads1:
        for fragment_spread1 in fragment_spreads1:
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                rule_context,
                conflicts,
                are_mutually_exclusive,
                collect_fields_result2,
                scope2,
                fragment_spread1,
            )

    # (J) Also collect conflicts between any fragment spreads by the first and fragment
    # spreads by the second. This compares each item in the first set of spreads to each
    # item in the second set of spreads.
    for fragment_spread1 in fragment_spreads1:
        for fragment_spread2 in fragment_spreads2:
            collect_conflicts_between_fragments(
                validation_context,
                rule_context,
                conflicts,
                are_mutually_exclusive,
                fragment_spread1,
                fragment_spread2,
            )

    return conflicts


def collect_conflicts_within(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    conflicts: list[Conflict],
    collect_fields_result: CollectFieldsResult,
    scope: VariableScope | None,
) -> None:
    """Collect all Conflicts "within" one collection of fields."""
    # A field map is a keyed collection, where each key represents a response name and
    # the value at that key is a list of all fields which provide that response name.
    # For every response name, if there are multiple fields, they must be compared to
    # find a potential conflict.
    grouped_field_set = collect_fields_result.grouped_field_set
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
                        scope,
                        other_field_details,
                        scope,
                    )
                    if conflict:
                        conflicts.append(conflict)


def collect_conflicts_between(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    conflicts: list[Conflict],
    parent_fields_are_mutually_exclusive: bool,
    collect_fields_result1: CollectFieldsResult,
    scope1: VariableScope | None,
    collect_fields_result2: CollectFieldsResult,
    scope2: VariableScope | None,
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
    for (
        response_name,
        field_details_list1,
        field_details_list2,
    ) in get_overlapping_fields(
        rule_context, collect_fields_result1, collect_fields_result2
    ):
        for field_details1 in field_details_list1:
            for field_details2 in field_details_list2:
                conflict = find_conflict(
                    validation_context,
                    rule_context,
                    parent_fields_are_mutually_exclusive,
                    response_name,
                    field_details1,
                    scope1,
                    field_details2,
                    scope2,
                )
                if conflict:
                    conflicts.append(conflict)


def get_overlapping_fields(
    rule_context: RuleContext,
    collect_fields_result1: CollectFieldsResult,
    collect_fields_result2: CollectFieldsResult,
) -> list[OverlappingFields]:
    """Get the fields of two collections that have the same response name.

    Matching response names is independent of variable scopes. Reuse that matching
    across scopes, while still comparing fields in their own scope.
    """
    by_collect_fields_result = collect_fields_result1.overlapping_fields
    if by_collect_fields_result is None:
        by_collect_fields_result = collect_fields_result1.overlapping_fields = {}
    cached = by_collect_fields_result.get(collect_fields_result2)
    if cached is not None:
        return cached
    overlapping_fields: list[OverlappingFields] = []
    grouped_field_set2 = collect_fields_result2.grouped_field_set
    for (
        response_name,
        field_details_list1,
    ) in collect_fields_result1.grouped_field_set.items():
        # A field map can participate in many distinct comparisons.
        spend_complexity_budget(rule_context, 1)
        field_details_list2 = grouped_field_set2.get(response_name)
        if field_details_list2:
            overlapping_fields.append(
                OverlappingFields(
                    response_name, field_details_list1, field_details_list2
                )
            )
    by_collect_fields_result[collect_fields_result2] = overlapping_fields
    return overlapping_fields


def find_conflict(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    parent_fields_are_mutually_exclusive: bool,
    response_name: str,
    field_details1: FieldDetails,
    scope1: VariableScope | None,
    field_details2: FieldDetails,
    scope2: VariableScope | None,
) -> Conflict | None:
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
    type1 = cast("GraphQLOutputType | None", def1 and def1.type)
    type2 = cast("GraphQLOutputType | None", def2 and def2.type)

    # Count attempted field pairs, including pairs skipped by type exclusivity.
    spend_complexity_budget(rule_context, 2)
    field_info1 = get_field_info(field_details1)
    field_info2 = get_field_info(field_details2)
    comparison = field_info1.comparisons.get(field_info2)
    if comparison is None:
        comparison = field_info1.comparisons[field_info2] = FieldComparison()

    if not are_mutually_exclusive:
        # Two aliases must refer to the same field.
        name1 = node1.name.value
        name2 = node2.name.value
        # Field names do not depend on the fragment scope.
        same_name = comparison.same_name
        if same_name is None:
            same_name = comparison.same_name = name1 == name2
        if not same_name:
            return Conflict(
                response_name,
                f"'{maybe_abbreviate(name1)}' and '{maybe_abbreviate(name2)}'"
                " are different fields",
                [node1],
                [node2],
            )

        # Two field calls must have the same arguments.
        compared_arguments = comparison.arguments
        if compared_arguments is None:
            compared_arguments = comparison.arguments = compare_arguments(
                rule_context, field_info1.arguments, field_info2.arguments
            )
        if not same_arguments(rule_context, compared_arguments, scope1, scope2):
            return Conflict(
                response_name, "they have differing arguments", [node1], [node2]
            )

    if field_info1.has_stream or field_info2.has_stream:
        reason = "they have overlapping stream directives"
        if field_info1.has_stream and field_info2.has_stream:
            compared_arguments = comparison.stream_arguments
            if compared_arguments is None:
                compared_arguments = comparison.stream_arguments = compare_arguments(
                    rule_context,
                    field_info1.stream_arguments,
                    field_info2.stream_arguments,
                )
            if same_arguments(rule_context, compared_arguments, scope1, scope2):
                # This was allowed in previous alpha versions of GraphQL.js.
                reason += (
                    ". See https://github.com/graphql/defer-stream-wg/discussions/100"
                )
        return Conflict(response_name, reason, [node1], [node2])

    if type1 and type2 and do_types_conflict(type1, type2):
        return Conflict(
            response_name,
            f"they return conflicting types '{type1}' and '{type2}'",
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
            validation_context,
            rule_context,
            are_mutually_exclusive,
            get_named_type(type1),
            selection_set1,
            scope1,
            get_named_type(type2),
            selection_set2,
            scope2,
        )
        return subfield_conflicts(conflicts, response_name, node1, node2)

    return None  # no conflict


def get_field_info(field_details: FieldDetails) -> FieldInfo:
    """Prepare argument and directive lookups only when a field overlaps."""
    info = field_details.info
    if info is None:
        node = field_details.node
        stream = next(
            (
                directive
                for directive in node.directives or ()
                if directive.name.value == "stream"
            ),
            None,
        )
        info = field_details.info = FieldInfo(
            get_argument_info(node.arguments),
            stream is not None,
            get_argument_info(stream.arguments) if stream else None,
        )
    return info


def get_argument_info(args: ArgumentNodes | None) -> ArgumentInfo | None:
    if not args:
        return None
    return ArgumentInfo(args, {arg.name.value: arg.value for arg in args})


def compare_arguments(
    rule_context: RuleContext,
    argument_info1: ArgumentInfo | None,
    argument_info2: ArgumentInfo | None,
) -> ArgumentComparison:
    """Compare names and source values once per field pair.

    Retain only values containing variables, whose meaning can differ between fragment
    scopes.
    """
    values_with_variables: list[ValueInfo] = []
    if argument_info1 is None:
        return ArgumentComparison(argument_info2 is None, values_with_variables)
    if argument_info2 is None or len(argument_info1.nodes) != len(argument_info2.nodes):
        return ArgumentComparison(False, values_with_variables)
    values2 = argument_info2.values
    for arg1 in argument_info1.nodes:
        # A prepared argument list can participate in many field-pair comparisons.
        spend_complexity_budget(rule_context, 1)
        value2 = values2.get(arg1.name.value)
        if value2 is None:
            return ArgumentComparison(False, values_with_variables)
        value_info1 = get_value_info(rule_context, arg1.value)
        if (
            value_info1.comparison_key
            != get_value_info(rule_context, value2).comparison_key
        ):
            return ArgumentComparison(False, values_with_variables)
        if value_info1.variables:
            values_with_variables.append(value_info1)
    return ArgumentComparison(True, values_with_variables)


def same_arguments(
    rule_context: RuleContext,
    comparison: ArgumentComparison,
    scope1: VariableScope | None,
    scope2: VariableScope | None,
) -> bool:
    if not comparison.same_structure:
        return False
    # Equal expressions refer to the same variables within a scope. Across scopes,
    # they agree only when every reference is an operation variable.
    if scope1 is not scope2:
        for value in comparison.values_with_variables:
            # Different scope pairs can revisit the same prepared values.
            spend_complexity_budget(rule_context, 1)
            if uses_local_variables(
                rule_context, value, scope1
            ) or uses_local_variables(rule_context, value, scope2):
                return False
    return True


class ValueInfo:
    """The comparison key and the variable names of a value node."""

    __slots__ = "comparison_key", "scope_dependencies", "variables"

    scope_dependencies: RefMap[FragmentSignature, bool] | None

    def __init__(self, comparison_key: str, variables: list[str]) -> None:
        self.comparison_key = comparison_key
        self.variables = variables
        self.scope_dependencies = None


def uses_local_variables(
    rule_context: RuleContext, value: ValueInfo, scope: VariableScope | None
) -> bool:
    if scope is None:
        return False
    # Declaration membership does not depend on the fragment arguments.
    dependencies = value.scope_dependencies
    if dependencies is None:
        dependencies = value.scope_dependencies = RefMap()
    signature = scope.signature
    cached = dependencies.get(signature)
    if cached is not None:
        return cached
    variable_definitions = signature.variable_definitions
    depends_on_scope = False
    for variable in value.variables:
        # A source value can be checked in several declaration contexts.
        spend_complexity_budget(rule_context, 1)
        if variable in variable_definitions:
            depends_on_scope = True
            break
    dependencies[signature] = depends_on_scope
    return depends_on_scope


def get_value_info(rule_context: RuleContext, value: ValueNode) -> ValueInfo:
    """Keep variable names in the representation and compare their scopes separately."""
    cached = rule_context.value_info_by_node.get(value)
    if cached is not None:
        return cached
    variables: list[str] = []
    comparison_key = json.dumps(
        get_value_structure(value, variables),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    value_info = ValueInfo(comparison_key, variables)
    rule_context.value_info_by_node[value] = value_info
    return value_info


VALUE_KIND_NAMES: dict[type[ValueNode], str] = {
    BooleanValueNode: "BooleanValue",
    EnumValueNode: "EnumValue",
    FloatValueNode: "FloatValue",
    IntValueNode: "IntValue",
}


def get_value_structure(node: ValueNode, variables: list[str]) -> list[Any]:
    """Get a structure of nested lists that serializes like in GraphQL.js.

    The kind names are the ones of GraphQL.js, and object fields are ordered by name.
    The names of the variables are added to the given list.
    """
    if isinstance(node, VariableNode):
        variables.append(node.name.value)
        return ["Variable", node.name.value]
    if isinstance(node, ObjectValueNode):
        fields = sorted(node.fields, key=lambda field: field.name.value)
        return [
            "ObjectValue",
            [
                [field.name.value, get_value_structure(field.value, variables)]
                for field in fields
            ],
        ]
    if isinstance(node, ListValueNode):
        return [
            "ListValue",
            [get_value_structure(value, variables) for value in node.values],
        ]
    if isinstance(node, StringValueNode):
        return ["StringValue", node.value, node.block is True]
    if isinstance(node, NullValueNode):
        return ["NullValue", None]
    return [VALUE_KIND_NAMES[type(node)], node.value]  # type: ignore


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


def collect_fields(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    parent_type: GraphQLNamedType | None,
    selection_set: SelectionSetNode,
) -> CollectFieldsResult:
    """Get fields and referenced fragment spreads

    Given a selection set, return the collection of fields (a mapping of response name
    to field nodes and definitions) as well as a list of fragment spreads referenced
    via fragment spreads. Share source fields across scopes; only resolving spreads
    depends on the scope.
    """
    cached_collect_fields_results = rule_context.cached_collect_fields_results
    # A programmatically built document can share a selection-set object between
    # different parent types; their field definitions must not share a cache entry.
    # Selection sets are compared by identity, because AST nodes are compared by value
    # and equal selection sets can occur in different fragments of one document.
    by_selection_set = cached_collect_fields_results.get(parent_type)
    if by_selection_set is None:
        by_selection_set = cached_collect_fields_results[parent_type] = RefMap()
    collect_fields_result = by_selection_set.get(selection_set)
    if collect_fields_result is None:
        grouped_field_set: GroupedFieldSet = {}
        spreads: list[FragmentSpreadNode] = []
        collect_fields_impl(
            validation_context,
            parent_type,
            selection_set,
            grouped_field_set,
            spreads,
        )
        collect_fields_result = CollectFieldsResult(grouped_field_set, spreads)
        by_selection_set[selection_set] = collect_fields_result
    return collect_fields_result


def collect_fragment_fields(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    fragment: FragmentDefinitionNode,
) -> CollectFieldsResult:
    """Get referenced fields and nested fragment spreads

    Given a reference to a fragment, return the represented collection of fields as well
    as a list of nested fragment spreads referenced via fragment spreads.
    """
    fragment_type = type_from_ast(validation_context.schema, fragment.type_condition)
    return collect_fields(
        validation_context,
        rule_context,
        fragment_type,
        fragment.selection_set,
    )


def collect_fields_impl(
    validation_context: ValidationContext,
    parent_type: GraphQLNamedType | None,
    selection_set: SelectionSetNode,
    grouped_field_set: GroupedFieldSet,
    fragment_spreads: list[FragmentSpreadNode],
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
            field_details_list = grouped_field_set.get(response_name)
            if not field_details_list:
                field_details_list = grouped_field_set[response_name] = []
            field_details_list.append(FieldDetails(parent_type, selection, field_def))
        elif isinstance(selection, FragmentSpreadNode):
            fragment_spreads.append(selection)
        elif isinstance(selection, InlineFragmentNode):  # pragma: no branch
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
                fragment_spreads,
            )


def get_fragment_spreads(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    collect_fields_result: CollectFieldsResult,
    scope: VariableScope | None,
) -> list[FragmentSpread]:
    """Resolve the spreads of a source collection in the enclosing variable scope."""
    by_scope = collect_fields_result.by_scope
    if by_scope is None:
        by_scope = collect_fields_result.by_scope = {}
    cached = by_scope.get(scope)
    if cached is not None:
        return cached

    spreads_by_scope: dict[
        VariableScope | None, RefMap[FragmentDefinitionNode | None, FragmentSpread]
    ] = {}
    result: list[FragmentSpread] = []
    for spread_node in collect_fields_result.spreads:
        spread = get_fragment_spread(
            validation_context, rule_context, spread_node, scope
        )
        by_definition = spreads_by_scope.get(spread.scope)
        if by_definition is None:
            by_definition = spreads_by_scope[spread.scope] = RefMap()
        previous = by_definition.get(spread.definition)
        if previous is None:
            by_definition[spread.definition] = spread
            result.append(spread)
        else:
            # Keep first-occurrence order and the last occurrence's error location.
            previous.node = spread.node
    by_scope[scope] = result
    return result


def get_fragment_spread(
    validation_context: ValidationContext,
    rule_context: RuleContext,
    fragment_spread_node: FragmentSpreadNode,
    scope: VariableScope | None,
) -> FragmentSpread:
    """Build a fragment spread with its fragment definition and variable scope."""
    # New enclosing scopes can repeat spread resolution, including cache hits.
    spend_complexity_budget(rule_context, 1)
    fragment_spread_info = rule_context.fragment_spread_info_by_node.get(
        fragment_spread_node
    )
    if fragment_spread_info is None:
        signature = validation_context.get_fragment_signature_by_name()(
            fragment_spread_node.name.value
        )
        argument_info = get_argument_info(fragment_spread_node.arguments)
        parts: list[str] = []
        values: list[ValueInfo] = []
        if signature and argument_info is not None:
            arg_map = argument_info.values
            variable_definitions = signature.variable_definitions
            # Order only supplied, declared arguments, once per source spread.
            for name in sorted(
                name for name in arg_map if name in variable_definitions
            ):
                argument = get_value_info(rule_context, arg_map[name])
                parts += (name, argument.comparison_key)
                if argument.variables:
                    values.append(argument)
        fragment_spread_info_key = json.dumps(
            [signature.definition.name.value if signature else None, parts],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        fragment_spread_info = rule_context.fragment_spread_info_by_key.get(
            fragment_spread_info_key
        )
        if fragment_spread_info is None:
            fragment_spread_info = FragmentSpreadInfo(signature, values)
            rule_context.fragment_spread_info_by_key[fragment_spread_info_key] = (
                fragment_spread_info
            )
        rule_context.fragment_spread_info_by_node[fragment_spread_node] = (
            fragment_spread_info
        )

    # The source key fixes the variable names. Any local reference identifies
    # the enclosing scope; otherwise all references are operation variables.
    variable_scope = None
    for value in fragment_spread_info.values:
        # Enclosing scopes can revisit these prepared argument values.
        spend_complexity_budget(rule_context, 1)
        if uses_local_variables(rule_context, value, scope):
            variable_scope = scope
            break
    by_scope = fragment_spread_info.by_scope
    signature = fragment_spread_info.signature
    if variable_scope in by_scope:
        fragment_scope = by_scope[variable_scope]
    else:
        fragment_scope = by_scope[variable_scope] = get_variable_scope(signature)
    return FragmentSpread(
        fragment_spread_node,
        fragment_scope,
        signature.definition if signature else None,
    )


def get_variable_scope(
    fragment_signature: FragmentSignature | None,
) -> VariableScope | None:
    if not fragment_signature or not fragment_signature.variable_definitions:
        return None
    return VariableScope(fragment_signature)


def get_fragment_spread_description(
    rule_context: RuleContext, node: FragmentSpreadNode
) -> str:
    """Print the fragment spread without its directives and the leading dots."""
    name = maybe_abbreviate(node.name.value)
    # Use the cached representation's length to print only small arguments.
    size = 1
    for argument in node.arguments or ():
        size += (
            2
            + len(argument.name.value)
            + len(get_value_info(rule_context, argument.value).comparison_key)
        )
        if size > MAX_FRAGMENT_ARGUMENT_SIZE:
            return name + "(...)"
    return print_ast(
        FragmentSpreadNode(name=NameNode(value=name), arguments=node.arguments)
    )[3:]


def subfield_conflicts(
    conflicts: list[Conflict], response_name: str, node1: FieldNode, node2: FieldNode
) -> Conflict | None:
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
    node: FieldNode, conflict_fields: list[list[FieldNode]]
) -> list[FieldNode]:
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


def spend_complexity_budget(rule_context: RuleContext, cost: int) -> None:
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


class OrderedPairSet:
    """Ordered pair set

    A way to keep track of pairs of things where the ordering of the pair matters.

    Provides a third argument for has/add to allow flagging the pair as weakly or
    strongly present within the collection.

    The elements are matched by object identity (their ``id``), because AST nodes are
    compared by value. They are kept alive for the duration of the validation.
    """

    __slots__ = ("_data",)

    _data: dict[int, dict[int, bool]]

    def __init__(self) -> None:
        self._data = {}

    def has(self, a: object, b: object, weakly_present: bool) -> bool:
        map_ = self._data.get(id(a))
        if map_ is None:
            return False
        result = map_.get(id(b))
        if result is None:
            return False

        return True if weakly_present else weakly_present == result

    def add(self, a: object, b: object, weakly_present: bool) -> None:
        map_ = self._data.get(id(a))
        if map_ is None:
            self._data[id(a)] = {id(b): weakly_present}
        else:
            map_[id(b)] = weakly_present


class PairSet:
    """Pair set

    A way to keep track of pairs of things when the ordering of the pair doesn't matter.
    """

    __slots__ = ("_ordered_pair_set",)

    def __init__(self) -> None:
        self._ordered_pair_set = OrderedPairSet()

    def has(self, a: object, b: object, weakly_present: bool) -> bool:
        # weakly_present being False is a superset of being True, hence if we want to
        # know if this PairSet "has" these two with no exclusivity, we have to ensure
        # it was added as such.
        return self._ordered_pair_set.has(
            a, b, weakly_present
        ) or self._ordered_pair_set.has(b, a, weakly_present)

    def add(self, a: object, b: object, weakly_present: bool) -> None:
        self._ordered_pair_set.add(a, b, weakly_present)
