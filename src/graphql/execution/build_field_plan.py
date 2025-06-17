"""Build field plan"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Dict, NamedTuple

from ..pyutils import RefMap, RefSet
from .collect_fields import DeferUsage, FieldDetails

if TYPE_CHECKING:
    from ..language import FieldNode

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

__all__ = [
    "DeferUsageSet",
    "FieldGroup",
    "FieldPlan",
    "GroupedFieldSet",
    "NewGroupedFieldSetDetails",
    "build_field_plan",
]


DeferUsageSet: TypeAlias = RefSet[DeferUsage]


class FieldGroup(NamedTuple):
    """A group of fields with defer usages."""

    fields: list[FieldDetails]
    defer_usages: DeferUsageSet | None = None
    known_defer_usages: DeferUsageSet | None = None

    def to_nodes(self) -> list[FieldNode]:
        """Return the field nodes in this group."""
        return [field_details.node for field_details in self.fields]


if sys.version_info < (3, 9):
    GroupedFieldSet: TypeAlias = Dict[str, FieldGroup]
else:  # Python >= 3.9
    GroupedFieldSet: TypeAlias = dict[str, FieldGroup]


class NewGroupedFieldSetDetails(NamedTuple):
    """Details of a new grouped field set."""

    grouped_field_set: GroupedFieldSet
    should_initiate_defer: bool


class FieldPlan(NamedTuple):
    """A plan for executing fields."""

    grouped_field_set: GroupedFieldSet
    new_grouped_field_set_details_map: RefMap[DeferUsageSet, NewGroupedFieldSetDetails]
    new_defer_usages: list[DeferUsage]


def build_field_plan(
    fields: dict[str, list[FieldDetails]],
    parent_defer_usages: DeferUsageSet | None = None,
    known_defer_usages: DeferUsageSet | None = None,
) -> FieldPlan:
    """Build a plan for executing fields."""
    if parent_defer_usages is None:
        parent_defer_usages = RefSet()
    if known_defer_usages is None:
        known_defer_usages = RefSet()

    new_defer_usages: RefSet[DeferUsage] = RefSet()
    new_known_defer_usages: RefSet[DeferUsage] = RefSet(known_defer_usages)

    grouped_field_set: GroupedFieldSet = {}

    new_grouped_field_set_details_map: RefMap[
        DeferUsageSet, NewGroupedFieldSetDetails
    ] = RefMap()

    map_: dict[str, tuple[DeferUsageSet, list[FieldDetails]]] = {}

    for response_key, field_details_list in fields.items():
        defer_usage_set: RefSet[DeferUsage] = RefSet()
        in_original_result = False
        for field_details in field_details_list:
            defer_usage = field_details.defer_usage
            if defer_usage is None:
                in_original_result = True
                continue
            defer_usage_set.add(defer_usage)
            if defer_usage not in known_defer_usages:
                new_defer_usages.add(defer_usage)
                new_known_defer_usages.add(defer_usage)
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
        map_[response_key] = (defer_usage_set, field_details_list)

    for response_key, [defer_usage_set, field_details_list] in map_.items():
        if defer_usage_set == parent_defer_usages:
            field_group = grouped_field_set.get(response_key)
            if field_group is None:  # pragma: no cover else
                field_group = FieldGroup([], defer_usage_set, new_known_defer_usages)
                grouped_field_set[response_key] = field_group
            field_group.fields.extend(field_details_list)
            continue

        for (
            new_grouped_field_set_defer_usage_set,
            new_grouped_field_set_details,
        ) in new_grouped_field_set_details_map.items():
            if new_grouped_field_set_defer_usage_set == defer_usage_set:
                new_grouped_field_set = new_grouped_field_set_details.grouped_field_set
                break
        else:
            new_grouped_field_set = {}
            new_grouped_field_set_details = NewGroupedFieldSetDetails(
                new_grouped_field_set,
                any(
                    defer_usage not in parent_defer_usages
                    for defer_usage in defer_usage_set
                ),
            )
            new_grouped_field_set_details_map[defer_usage_set] = (
                new_grouped_field_set_details
            )

        field_group = new_grouped_field_set.get(response_key)
        if field_group is None:  # pragma: no cover else
            field_group = FieldGroup([], defer_usage_set, new_known_defer_usages)
            new_grouped_field_set[response_key] = field_group
        field_group.fields.extend(field_details_list)

    return FieldPlan(
        grouped_field_set, new_grouped_field_set_details_map, list(new_defer_usages)
    )
