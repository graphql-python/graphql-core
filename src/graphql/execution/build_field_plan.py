"""Build field plan"""

from __future__ import annotations

from typing import NamedTuple, TypeAlias

from ..pyutils import RefMap, RefSet
from .collect_fields import DeferUsage, FieldGroup, GroupedFieldSet

__all__ = [
    "DeferUsageSet",
    "FieldPlan",
    "GroupedFieldSet",
    "build_field_plan",
]


DeferUsageSet: TypeAlias = RefSet[DeferUsage]


class FieldPlan(NamedTuple):
    """A plan for executing fields."""

    grouped_field_set: GroupedFieldSet
    new_grouped_field_sets: RefMap[DeferUsageSet, GroupedFieldSet]


def build_field_plan(
    original_grouped_field_set: GroupedFieldSet,
    parent_defer_usages: DeferUsageSet | None = None,
) -> FieldPlan:
    """Build a plan for executing fields."""
    if parent_defer_usages is None:
        parent_defer_usages = RefSet()

    grouped_field_set: GroupedFieldSet = {}
    new_grouped_field_sets: RefMap[DeferUsageSet, GroupedFieldSet] = RefMap()

    for response_key, field_group in original_grouped_field_set.items():
        filtered_defer_usage_set = get_filtered_defer_usage_set(field_group)

        if filtered_defer_usage_set == parent_defer_usages:
            grouped_field_set[response_key] = field_group
            continue

        for defer_usage_set in new_grouped_field_sets:
            if defer_usage_set == filtered_defer_usage_set:
                new_grouped_field_set = new_grouped_field_sets[defer_usage_set]
                break
        else:
            new_grouped_field_set = {}
            new_grouped_field_sets[filtered_defer_usage_set] = new_grouped_field_set

        new_grouped_field_set[response_key] = field_group

    return FieldPlan(grouped_field_set, new_grouped_field_sets)


def get_filtered_defer_usage_set(field_group: FieldGroup) -> RefSet[DeferUsage]:
    """Get a filtered set of defer usages."""
    # Create the set of defer usages for the field group.
    filtered_defer_usage_set: RefSet[DeferUsage] = RefSet()
    for field_details in field_group:
        defer_usage = field_details.defer_usage
        if defer_usage is None:
            filtered_defer_usage_set.clear()
            return filtered_defer_usage_set
        filtered_defer_usage_set.add(defer_usage)

    # Remove defer usages that have a parent defer usage in the set.
    # Since we remove in place, we need to iterate over a copy of the set.
    for defer_usage in tuple(filtered_defer_usage_set):
        parent_defer_usage: DeferUsage | None = defer_usage.parent_defer_usage
        while parent_defer_usage is not None:
            if parent_defer_usage in filtered_defer_usage_set:
                filtered_defer_usage_set.discard(defer_usage)
                break
            parent_defer_usage = parent_defer_usage.parent_defer_usage

    return filtered_defer_usage_set
