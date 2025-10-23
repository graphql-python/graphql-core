"""Build field plan"""

from __future__ import annotations

from typing import NamedTuple

from ..pyutils import RefMap, RefSet
from .collect_fields import DeferUsage, FieldGroup, GroupedFieldSet

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

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

    map_: dict[str, tuple[DeferUsageSet, FieldGroup]] = {}

    for response_key, field_group in original_grouped_field_set.items():
        defer_usage_set: RefSet[DeferUsage] = RefSet()
        in_original_result = False
        for field_details in field_group:
            defer_usage = field_details.defer_usage
            if defer_usage is None:
                in_original_result = True
                continue
            defer_usage_set.add(defer_usage)
        if in_original_result:
            defer_usage_set.clear()
        else:
            defer_usage_set -= {
                defer_usage
                for defer_usage in defer_usage_set
                if any(
                    ancestor in defer_usage_set for ancestor in defer_usage.ancestors
                )
            }
        map_[response_key] = (defer_usage_set, field_group)

    for response_key, [defer_usage_set, field_group] in map_.items():
        if defer_usage_set == parent_defer_usages:
            grouped_field_set[response_key] = field_group
            continue

        for (
            new_grouped_field_set_defer_usage_set,
            new_grouped_field_set_field_group,
        ) in new_grouped_field_sets.items():  # pragma: no branch
            if new_grouped_field_set_defer_usage_set == defer_usage_set:
                new_grouped_field_set = new_grouped_field_set_field_group
                break
        else:
            new_grouped_field_set = {}
            new_grouped_field_sets[defer_usage_set] = new_grouped_field_set

        new_grouped_field_set[response_key] = field_group

    return FieldPlan(grouped_field_set, new_grouped_field_sets)
