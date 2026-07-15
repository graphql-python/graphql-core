"""Executor throwing on incremental delivery"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..error import GraphQLError
from ..language import OperationType
from .executor import (
    DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS,
    UNEXPECTED_MULTIPLE_PAYLOADS,
    Executor,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Iterable, Sequence

    from ..pyutils import AwaitableOrValue, Path
    from ..type import (
        GraphQLList,
        GraphQLObjectType,
        GraphQLOutputType,
        GraphQLResolveInfo,
    )
    from .collect_fields import DeferUsage, FieldDetailsList, GroupedFieldSet

__all__ = [
    "ExecutorThrowingOnIncremental",
]


class ExecutorThrowingOnIncremental(Executor[None]):
    """Executor raising an error when the operation would defer or stream.

    For internal use only.
    """

    def execute_collected_root_fields(
        self,
        root_type: GraphQLObjectType,
        root_value: Any,
        grouped_field_set: GroupedFieldSet,
        serially: bool,
        new_defer_usages: Sequence[DeferUsage],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the collected root fields, raising if something is deferred."""
        if new_defer_usages:
            if self.operation.operation == OperationType.SUBSCRIPTION:
                raise GraphQLError(DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS)
            raise GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)
        return self.execute_root_grouped_field_set(
            root_type,
            root_value,
            grouped_field_set,
            serially,
            None,
        )

    def execute_collected_subfields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path,
        grouped_field_set: GroupedFieldSet,
        new_defer_usages: Sequence[DeferUsage],
        position_context: None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the collected subfields, raising if something is deferred."""
        if new_defer_usages:
            if self.operation.operation == OperationType.SUBSCRIPTION:
                raise GraphQLError(DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS)
            raise GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)

        return self.execute_fields(
            parent_type,
            source_value,
            path,
            grouped_field_set,
            None,
        )

    def complete_list_value(
        self,
        return_type: GraphQLList[GraphQLOutputType],
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        result: AsyncIterable[Any] | Iterable[Any],
        position_context: None,
    ) -> AwaitableOrValue[list[Any]]:
        """Complete a list value, raising if something is streamed."""
        # this raises located errors when `@stream` is used on subscriptions
        stream_usage = self.get_stream_usage(field_details_list, path)
        if stream_usage is not None:
            raise GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)

        return super().complete_list_value(
            return_type,
            field_details_list,
            info,
            path,
            result,
            position_context,
        )
