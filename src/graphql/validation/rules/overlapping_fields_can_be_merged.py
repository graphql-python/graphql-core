"""Overlapping fields can be merged rule"""

from itertools import chain
from typing import Any, Dict, List, NamedTuple, Optional, Union, cast

from ...error import GraphQLError
from ...language import (
    DirectiveNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    SelectionSetNode,
    ValueNode,
    print_ast,
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
from ...utilities.sort_value_node import sort_value_node
from . import ValidationContext, ValidationRule

MYPY = False

__all__ = ["MAX_FIELD_COMPARISONS", "OverlappingFieldsCanBeMergedRule"]

# The maximum number of pairwise field comparisons performed while validating a
# single document with the OverlappingFieldsCanBeMerged rule. The rule compares
# every pair of fields that share a response name and recurses into their
# sub-selections, which is O(n^2) in the number of such fields (and worse when
# inline fragments repeat the same response name at multiple nesting levels). A
# crafted query can therefore drive validation into minutes of CPU on a single
# request. Once this many comparisons have been made, validation is aborted with a
# GraphQLError instead of running to completion. The default is high enough that any
# realistic query stays far below it; it can be raised or lowered by assigning to
# ``graphql.validation.rules.overlapping_fields_can_be_merged.MAX_FIELD_COMPARISONS``.
MAX_FIELD_COMPARISONS = 250_000


class ComparisonBudgetExceededError(Exception):
    """Internal signal that the field-comparison budget has been exhausted.

    Raised deep inside the recursive conflict search and caught by the rule to abort
    validation. Never surfaces to callers of ``validate``.
    """


def reason_message(reason: "ConflictReasonMessage") -> str:
    if isinstance(reason, list):
        return " and ".join(
            f"subfields '{sub_reason.response_name}' conflict"
            f" because {reason_message(sub_reason.reason)}"
            for sub_reason in reason
        )
    return reason


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

        # Set once the comparison budget is exhausted. Further selection sets are then
        # skipped, since validation has already been aborted with an error.
        self._budget_exceeded = False

    def enter_selection_set(self, selection_set: SelectionSetNode, *_args: Any) -> None:
        """Called when entering a selection set node.

        :meta private:
        """
        if self._budget_exceeded:
            return
        try:
            conflicts = find_conflicts_within_selection_set(
                self.context,
                self.rule_context,
                self.context.get_parent_type(),
                selection_set,
            )
        except ComparisonBudgetExceededError:
            self._budget_exceeded = True
            self.report_error(
                GraphQLError(
                    "Query is too complex to validate for overlapping fields:"
                    f" exceeded {MAX_FIELD_COMPARISONS} field comparisons."
                    " Validation was aborted.",
                    selection_set,
                )
            )
            return
        for response_name, reason, fields1, fields2 in conflicts:
            reason_msg = reason_message(reason)
            self.report_error(
                GraphQLError(
                    f"Fields '{response_name}' conflict because {reason_msg}."
                    " Use different aliases on the fields to fetch both"
                    " if this was intentional.",
                    fields1 + fields2,
                )
            )


# Reason is a string, or a nested list of conflicts.
if MYPY:  # recursive types not fully supported yet (/python/mypy/issues/731)
    ConflictReasonMessage = Union[str, List]
else:
    ConflictReasonMessage = Union[str, List["ConflictReason"]]


class ConflictReason(NamedTuple):
    """Field name and reason."""

    response_name: str
    reason: ConflictReasonMessage


class Conflict(NamedTuple):
    """A conflict with the field nodes on both sides."""

    response_name: str
    reason: ConflictReasonMessage
    fields1: List[FieldNode]
    fields2: List[FieldNode]


class FieldDetails:
    """A field node and its definition in the parent-type context."""

    __slots__ = "definition", "node", "parent_type"

    def __init__(
        self,
        parent_type: Optional[GraphQLNamedType],
        node: FieldNode,
        definition: Optional[GraphQLField],
    ) -> None:
        self.parent_type = parent_type
        self.node = node
        self.definition = definition


FieldDetailsList = List[FieldDetails]
GroupedFieldSet = Dict[str, FieldDetailsList]


class CollectFieldsResult:
    """The fields and fragment names collected from a selection set."""

    __slots__ = "fragment_names", "grouped_field_set"

    def __init__(
        self, grouped_field_set: GroupedFieldSet, fragment_names: List[str]
    ) -> None:
        self.grouped_field_set = grouped_field_set
        self.fragment_names = fragment_names


class RuleContext:
    """The state of the rule that is shared during the validation of a document."""

    __slots__ = (
        "cached_collect_fields_results",
        "compared_fields_and_fragment_pairs",
        "compared_fragment_pairs",
        "field_comparisons",
    )

    def __init__(self) -> None:
        # A memoization for when fields and a fragment or two fragments are compared
        # "between" each other for conflicts. Comparisons may be made many times, so
        # memoizing this can dramatically improve the performance of this validator.
        self.compared_fields_and_fragment_pairs = OrderedPairSet()
        self.compared_fragment_pairs = PairSet()

        # A cache for the "field map" and list of fragment names found in any given
        # selection set.
        self.cached_collect_fields_results: Dict[
            SelectionSetNode, CollectFieldsResult
        ] = {}

        # The number of pairwise field comparisons made so far, which is limited by
        # the comparison budget.
        self.field_comparisons = 0


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
    spreading in fragments.

    Called when visiting each SelectionSet in the GraphQL Document.
    """
    conflicts: List[Conflict] = []

    collect_fields_result = collect_fields(
        validation_context, rule_context, parent_type, selection_set
    )
    grouped_field_set = collect_fields_result.grouped_field_set
    fragment_names = collect_fields_result.fragment_names

    # (A) Find all conflicts "within" the fields of this selection set.
    # Note: this is the *only place* `collect_conflicts_within` is called.
    collect_conflicts_within(
        validation_context,
        conflicts,
        rule_context,
        grouped_field_set,
    )

    if fragment_names:
        # (B) Then collect conflicts between these fields and those represented by each
        # spread fragment name found.
        for i, fragment_name in enumerate(fragment_names):
            collect_conflicts_between_fields_and_fragment(
                validation_context,
                conflicts,
                rule_context,
                False,
                grouped_field_set,
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
    grouped_field_set: GroupedFieldSet,
    fragment_name: str,
) -> None:
    """Collect conflicts between fields and fragment.

    Collect all conflicts found between a set of fields and a fragment reference
    including via spreading in any nested fragments.
    """
    if not grouped_field_set:
        return

    compared_fields_and_fragment_pairs = rule_context.compared_fields_and_fragment_pairs
    # Memoize so the fields and fragments are not compared for conflicts more
    # than once.
    if compared_fields_and_fragment_pairs.has(
        grouped_field_set, fragment_name, are_mutually_exclusive
    ):
        return
    compared_fields_and_fragment_pairs.add(
        grouped_field_set, fragment_name, are_mutually_exclusive
    )

    fragment = validation_context.get_fragment(fragment_name)
    if not fragment:
        return None

    collect_fields_result = collect_fragment_fields(
        validation_context, rule_context, fragment
    )
    grouped_field_set2 = collect_fields_result.grouped_field_set
    referenced_fragment_names = collect_fields_result.fragment_names

    # Do not compare a fragment's grouped_field_set to itself.
    if grouped_field_set is grouped_field_set2:
        return

    # (D) First collect any conflicts between the provided collection of fields and the
    # collection of fields represented by the given fragment.
    collect_conflicts_between(
        validation_context,
        conflicts,
        rule_context,
        are_mutually_exclusive,
        grouped_field_set,
        grouped_field_set2,
    )

    # (E) Then collect any conflicts between the provided collection of fields and any
    # fragment names found in the given fragment.
    for referenced_fragment_name in referenced_fragment_names:
        collect_conflicts_between_fields_and_fragment(
            validation_context,
            conflicts,
            rule_context,
            are_mutually_exclusive,
            grouped_field_set,
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
    grouped_field_set1 = collect_fields_result1.grouped_field_set
    referenced_fragment_names1 = collect_fields_result1.fragment_names

    collect_fields_result2 = collect_fragment_fields(
        validation_context, rule_context, fragment2
    )
    grouped_field_set2 = collect_fields_result2.grouped_field_set
    referenced_fragment_names2 = collect_fields_result2.fragment_names

    # (F) First, collect all conflicts between these two collections of fields
    # (not including any nested fragments)
    collect_conflicts_between(
        validation_context,
        conflicts,
        rule_context,
        are_mutually_exclusive,
        grouped_field_set1,
        grouped_field_set2,
    )

    # (G) Then collect conflicts between the first fragment and any nested fragments
    # spread in the second fragment.
    for referenced_fragment_name2 in referenced_fragment_names2:
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
    for referenced_fragment_name1 in referenced_fragment_names1:
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
    grouped_field_set1 = collect_fields_result1.grouped_field_set
    fragment_names1 = collect_fields_result1.fragment_names

    collect_fields_result2 = collect_fields(
        validation_context, rule_context, parent_type2, selection_set2
    )
    grouped_field_set2 = collect_fields_result2.grouped_field_set
    fragment_names2 = collect_fields_result2.fragment_names

    # (H) First, collect all conflicts between these two collections of field.
    collect_conflicts_between(
        validation_context,
        conflicts,
        rule_context,
        are_mutually_exclusive,
        grouped_field_set1,
        grouped_field_set2,
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
                grouped_field_set1,
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
                grouped_field_set2,
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
    grouped_field_set1: GroupedFieldSet,
    grouped_field_set2: GroupedFieldSet,
) -> None:
    """Collect all Conflicts between two collections of fields.

    This is similar to, but different from the :func:`~.collect_conflicts_within`
    function above. This check assumes that :func:`~.collect_conflicts_within` has
    already been called on each provided collection of fields. This is true because
    this validator traverses each individual selection set.
    """
    if not grouped_field_set1 or not grouped_field_set2:
        return

    # A field map is a keyed collection, where each key represents a response name and
    # the value at that key is a list of all fields which provide that response name.
    # For any response name which appears in both provided field maps, each field from
    # the first field map must be compared to every field in the second field map to
    # find potential conflicts.
    for response_name, field_details_list1 in grouped_field_set1.items():
        field_details_list2 = grouped_field_set2.get(response_name)
        if field_details_list2:
            for field_details1 in field_details_list1:
                for field_details2 in field_details_list2:
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
    # Charge this comparison against the document-wide budget and abort validation once
    # it is exhausted, guarding against quadratic-blowup denial of service.
    rule_context.field_comparisons += 1
    if rule_context.field_comparisons > MAX_FIELD_COMPARISONS:
        raise ComparisonBudgetExceededError

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

    if not are_mutually_exclusive:
        # Two aliases must refer to the same field.
        name1 = node1.name.value
        name2 = node2.name.value
        if name1 != name2:
            return Conflict(
                response_name,
                f"'{name1}' and '{name2}' are different fields",
                [node1],
                [node2],
            )

        # Two field calls must have the same arguments.
        if not same_arguments(node1, node2):
            return Conflict(
                response_name, "they have differing arguments", [node1], [node2]
            )

    if type1 and type2 and do_types_conflict(type1, type2):
        return Conflict(
            response_name,
            f"they return conflicting types '{type1}' and '{type2}'",
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
            get_named_type(type1),
            selection_set1,
            get_named_type(type2),
            selection_set2,
        )
        return subfield_conflicts(conflicts, response_name, node1, node2)

    return None  # no conflict


def same_arguments(
    node1: Union[FieldNode, DirectiveNode], node2: Union[FieldNode, DirectiveNode]
) -> bool:
    args1 = node1.arguments
    args2 = node2.arguments

    if not args1:
        return not args2

    if not args2:
        return False

    if len(args1) != len(args2):
        return False  # pragma: no cover

    values2 = {arg.name.value: arg.value for arg in args2}

    for arg1 in args1:
        value1 = arg1.value
        value2 = values2.get(arg1.name.value)
        if value2 is None or stringify_value(value1) != stringify_value(value2):
            return False

    return True


def stringify_value(value: ValueNode) -> str:
    return print_ast(sort_value_node(value))


def do_types_conflict(type1: GraphQLOutputType, type2: GraphQLOutputType) -> bool:
    """Check whether two types conflict

    Two types conflict if both types could not apply to a value simultaneously.
    Composite types are ignored as their individual field types will be compared later
    recursively. However List and Non-Null types must match.
    """
    if is_list_type(type1):
        return (
            do_types_conflict(
                cast(GraphQLList, type1).of_type, cast(GraphQLList, type2).of_type
            )
            if is_list_type(type2)
            else True
        )
    if is_list_type(type2):
        return True
    if is_non_null_type(type1):
        return (
            do_types_conflict(
                cast(GraphQLNonNull, type1).of_type, cast(GraphQLNonNull, type2).of_type
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
    cached = cached_collect_fields_results.get(selection_set)
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
        cached_collect_fields_results[selection_set] = cached
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
    cached_collect_fields_results = rule_context.cached_collect_fields_results
    # Short-circuit building a type from the node if possible.
    cached = cached_collect_fields_results.get(fragment.selection_set)
    if cached is not None:
        return cached

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
            field_details_list.append(FieldDetails(parent_type, selection, field_def))
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
        return Conflict(
            response_name,
            [
                ConflictReason(conflict.response_name, conflict.reason)
                for conflict in conflicts
            ],
            list(chain([node1], *[conflict.fields1 for conflict in conflicts])),
            list(chain([node2], *[conflict.fields2 for conflict in conflicts])),
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

    _data: Dict[int, Dict[str, bool]]

    def __init__(self) -> None:
        self._data = {}

    def has(self, a: GroupedFieldSet, b: str, weakly_present: bool) -> bool:
        map_ = self._data.get(id(a))
        if map_ is None:
            return False
        result = map_.get(b)
        if result is None:
            return False

        return True if weakly_present else weakly_present == result

    def add(self, a: GroupedFieldSet, b: str, weakly_present: bool) -> None:
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
