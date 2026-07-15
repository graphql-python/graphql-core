"""Incremental GraphQL executor"""

from __future__ import annotations

from asyncio import ensure_future, gather
from contextlib import suppress
from copy import copy
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from ...error import GraphQLError, located_error
from ...language import OperationType
from ...pyutils import RefMap
from ..executor import (
    DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS,
    CollectedErrors,
    Executor,
    collect_iterator_awaitables,
    to_nodes,
)
from .build_execution_plan import build_execution_plan
from .computation import Computation
from .incremental_publisher import IncrementalPublisher
from .stream_item_queue import StreamItemQueue
from .work_queue import Work, WorkResult, WorkTask

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Sequence

    from ...pyutils import AwaitableOrValue, Path
    from ...type import (
        GraphQLObjectType,
        GraphQLOutputType,
        GraphQLResolveInfo,
    )
    from ..collect_fields import (
        DeferUsage,
        FieldDetailsList,
        GroupedFieldSet,
    )
    from ..executor import StreamUsage
    from ..types import ExecutionResult, ExperimentalIncrementalExecutionResults
    from .build_execution_plan import DeferUsageSet, ExecutionPlan
    from .work_queue import StreamQueue

__all__ = [
    "DeliveryGroup",
    "DeliveryGroupMap",
    "ExecutionGroup",
    "ExecutionGroupValue",
    "IncrementalExecutor",
    "ItemStream",
    "StreamItemValue",
    "should_defer",
]

suppress_exceptions = suppress(Exception)


class DeliveryGroup:
    """A deferred fragment addressable as a unit of delivery.

    Compared and hashed by identity, like all graph nodes.

    For internal use only.
    """

    __slots__ = "label", "parent", "path"

    path: Path | None
    label: str | None
    parent: DeliveryGroup | None

    def __init__(
        self,
        path: Path | None,
        label: str | None,
        parent: DeliveryGroup | None,
    ) -> None:
        self.path = path
        self.label = label
        self.parent = parent

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = []
        if self.path:
            args.append(f"path={self.path.as_list()!r}")
        if self.label:
            args.append(f"label={self.label!r}")
        if self.parent:
            args.append("parent")
        return f"{name}({', '.join(args)})"


DeliveryGroupMap = RefMap["DeferUsage", DeliveryGroup]


class ExecutionGroup(WorkTask):
    """A deferred grouped field set belonging to one or more delivery groups.

    For internal use only.
    """

    __slots__ = ("path",)

    path: Path | None

    def __init__(
        self,
        groups: Sequence[DeliveryGroup],
        computation: Computation[WorkResult],
        path: Path | None,
    ) -> None:
        super().__init__(groups, computation)
        self.path = path


class ItemStream:
    """A streamed list field backed by a queue of stream item results.

    Compared and hashed by identity, like all graph nodes.

    For internal use only.
    """

    __slots__ = "initial_count", "label", "path", "queue"

    path: Path
    label: str | None
    queue: StreamQueue  # a StreamItemQueue in practice
    initial_count: int

    def __init__(
        self,
        path: Path,
        label: str | None,
        queue: StreamItemQueue,
        initial_count: int,
    ) -> None:
        self.path = path
        self.label = label
        self.queue = queue
        self.initial_count = initial_count

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"path={self.path.as_list()!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{name}({', '.join(args)})"


class ExecutionGroupValue(NamedTuple):
    """The value produced by a completed execution group."""

    delivery_groups: Sequence[DeliveryGroup]
    path: list[str | int]
    data: dict[str, Any]
    errors: list[GraphQLError] | None = None


class StreamItemValue(NamedTuple):
    """The value produced by a completed stream item."""

    item: Any
    errors: list[GraphQLError] | None = None


class IncrementalExecutor(Executor[DeliveryGroupMap]):
    """Executor supporting incremental delivery via ``@defer`` and ``@stream``.

    Produces incremental work as data: each deferred grouped field set becomes
    an execution group wrapping its executable in a computation, and each
    streamed list field becomes an item stream owning a stream item queue.
    Each execution group and stream item is executed by a fresh sub-executor
    with its own collected errors, sharing the overall execution state.

    For internal use only.
    """

    defer_usage_set: DeferUsageSet | None
    groups: list[DeliveryGroup]
    tasks: list[ExecutionGroup]
    streams: list[ItemStream]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.defer_usage_set = None
        self.groups = []
        self.tasks = []
        self.streams = []
        # Execution plan memoization shared with all sub-executors
        self._initial_execution_plans: RefMap[GroupedFieldSet, ExecutionPlan] = RefMap()
        self._deferred_execution_plans: RefMap[
            GroupedFieldSet, list[tuple[DeferUsageSet, ExecutionPlan]]
        ] = RefMap()

    def create_sub_executor(
        self, defer_usage_set: DeferUsageSet | None = None
    ) -> IncrementalExecutor:
        """Create a sub-executor with fresh per-execution state.

        The sub-executor is a shallow copy sharing the overall execution
        state, with its own collected errors and produced incremental work.
        """
        sub_executor = copy(self)
        sub_executor.defer_usage_set = defer_usage_set
        sub_executor.collected_errors = CollectedErrors()
        sub_executor.groups = []
        sub_executor.tasks = []
        sub_executor.streams = []
        return sub_executor

    def abort(self, reason: BaseException | None = None) -> AwaitableOrValue[None]:
        """Abort the incremental work produced by this executor.

        Aborts the computations of all execution groups and the queues of all
        item streams produced by this executor, returning an awaitable for the
        asynchronous part of the cleanup, or None when the whole cleanup could
        be run synchronously.
        """
        awaitables: list[Any] = []
        is_awaitable = self.is_awaitable
        for task in self.tasks:
            abort_result = task.computation.abort(reason)
            if is_awaitable(abort_result):
                awaitables.append(abort_result)
        for stream in self.streams:
            abort_result = stream.queue.abort(reason)
            if is_awaitable(abort_result):
                awaitables.append(abort_result)
        if not awaitables:
            return None

        async def settle_awaitables() -> None:
            await gather(*awaitables, return_exceptions=True)

        return settle_awaitables()

    def abort_in_background(self, reason: BaseException | None = None) -> None:
        """Abort the produced incremental work, settling cleanup in background.

        Used on synchronous failure paths that cannot await the asynchronous
        part of the cleanup.
        """
        abort_result = self.abort(reason)
        if self.is_awaitable(abort_result):
            self.settle_in_background([abort_result])

    def build_response(
        self, data: dict[str, Any] | None
    ) -> ExecutionResult | ExperimentalIncrementalExecutionResults:
        """Build the response for the given completed initial data.

        When execution groups or item streams are still pending, an
        incremental response is built which delivers them via an incremental
        publisher; otherwise, the normal response is built.
        """
        work = self.get_incremental_work()
        if not work.tasks and not work.streams:
            return super().build_response(data)

        errors = self.collected_errors.errors
        incremental_publisher = IncrementalPublisher()
        return incremental_publisher.build_response(
            cast("dict[str, Any]", data), list(errors) or None, work, self
        )

    def execute_collected_root_fields(
        self,
        root_type: GraphQLObjectType,
        root_value: Any,
        grouped_field_set: GroupedFieldSet,
        serially: bool,
        new_defer_usages: Sequence[DeferUsage],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the collected root fields with incremental delivery."""
        if not new_defer_usages:
            return self.execute_root_grouped_field_set(
                root_type,
                root_value,
                grouped_field_set,
                serially,
                None,
            )

        if self.operation.operation == OperationType.SUBSCRIPTION:
            raise GraphQLError(DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS)

        new_delivery_groups, new_delivery_group_map = self.get_new_delivery_group_map(
            new_defer_usages, None, None
        )

        execution_plan = self.build_root_execution_plan(grouped_field_set)
        planned_field_set, new_grouped_field_sets = execution_plan

        data = self.execute_root_grouped_field_set(
            root_type,
            root_value,
            planned_field_set,
            serially,
            new_delivery_group_map,
        )

        self.groups.extend(new_delivery_groups)

        if new_grouped_field_sets:
            self.collect_execution_groups(
                root_type,
                root_value,
                None,
                new_grouped_field_sets,
                new_delivery_group_map,
            )

        return data

    def build_root_execution_plan(
        self, original_grouped_field_set: GroupedFieldSet
    ) -> ExecutionPlan:
        """Build a memoized execution plan for the root fields."""
        execution_plans = self._initial_execution_plans
        execution_plan = execution_plans.get(original_grouped_field_set)
        if execution_plan is None:
            execution_plan = build_execution_plan(original_grouped_field_set)
            execution_plans[original_grouped_field_set] = execution_plan
        return execution_plan

    def execute_collected_subfields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path,
        grouped_field_set: GroupedFieldSet,
        new_defer_usages: Sequence[DeferUsage],
        delivery_group_map: DeliveryGroupMap | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the collected subfields with incremental delivery."""
        if new_defer_usages and self.operation.operation == OperationType.SUBSCRIPTION:
            raise GraphQLError(DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS)

        if delivery_group_map is None and not new_defer_usages:
            return self.execute_fields(
                parent_type,
                source_value,
                path,
                grouped_field_set,
                delivery_group_map,
            )

        new_delivery_groups, new_delivery_group_map = self.get_new_delivery_group_map(
            new_defer_usages, delivery_group_map, path
        )

        execution_plan = self.build_sub_execution_plan(grouped_field_set)
        planned_field_set, new_grouped_field_sets = execution_plan

        data = self.execute_fields(
            parent_type,
            source_value,
            path,
            planned_field_set,
            new_delivery_group_map,
        )

        self.groups.extend(new_delivery_groups)

        if new_grouped_field_sets:
            self.collect_execution_groups(
                parent_type,
                source_value,
                path,
                new_grouped_field_sets,
                new_delivery_group_map,
            )

        return data

    def build_sub_execution_plan(
        self, original_grouped_field_set: GroupedFieldSet
    ) -> ExecutionPlan:
        """Build a memoized execution plan for the subfields."""
        defer_usage_set = self.defer_usage_set
        if defer_usage_set is None:
            return self.build_root_execution_plan(original_grouped_field_set)
        execution_plans = self._deferred_execution_plans
        planned = execution_plans.get(original_grouped_field_set)
        if planned is None:
            planned = []
            execution_plans[original_grouped_field_set] = planned
        else:
            for planned_defer_usage_set, execution_plan in planned:
                if planned_defer_usage_set is defer_usage_set:
                    return execution_plan
        execution_plan = build_execution_plan(
            original_grouped_field_set, defer_usage_set
        )
        planned.append((defer_usage_set, execution_plan))
        return execution_plan

    def collect_execution_groups(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        new_grouped_field_sets: RefMap[DeferUsageSet, GroupedFieldSet],
        delivery_group_map: DeliveryGroupMap,
    ) -> None:
        """Create execution groups for the new deferred grouped field sets."""
        append_task = self.tasks.append
        parent_defer_usages = self.defer_usage_set
        enable_early_execution = self.enable_early_execution
        for defer_usage_set, grouped_field_set in new_grouped_field_sets.items():
            delivery_groups = get_delivery_groups(defer_usage_set, delivery_group_map)

            sub_executor = self.create_sub_executor(defer_usage_set)

            def execute_group(
                sub_executor: IncrementalExecutor = sub_executor,
                delivery_groups: Sequence[DeliveryGroup] = delivery_groups,
                grouped_field_set: GroupedFieldSet = grouped_field_set,
            ) -> AwaitableOrValue[WorkResult]:
                return sub_executor.execute_execution_group(
                    delivery_groups,
                    parent_type,
                    source_value,
                    path,
                    grouped_field_set,
                    delivery_group_map,
                )

            computation = Computation(execute_group, sub_executor.abort)

            if enable_early_execution:
                if should_defer(parent_defer_usages, defer_usage_set):
                    self.prime_soon(computation)
                else:
                    self.prime_now(computation)

            append_task(ExecutionGroup(delivery_groups, computation, path))

    def prime_now(self, computation: Computation[WorkResult]) -> None:
        """Prime the computation immediately, tracking its pending future."""
        computation.prime()
        future = computation.pending_future
        if future is not None:
            self.track_incremental_future(future)

    def prime_soon(self, computation: Computation[WorkResult]) -> None:
        """Prime the computation early, but only after the current work.

        This makes sure that a new deferred execution group does not run
        before the execution step that created it has finished.
        """

        async def prime() -> None:
            self.prime_now(computation)

        self.track_incremental_future(ensure_future(prime()))

    def execute_execution_group(
        self,
        delivery_groups: Sequence[DeliveryGroup],
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        delivery_group_map: DeliveryGroupMap,
    ) -> AwaitableOrValue[WorkResult]:
        """Execute an execution group on this sub-executor."""
        try:
            result = self.execute_fields(
                parent_type,
                source_value,
                path,
                grouped_field_set,
                delivery_group_map,
            )
        except Exception:
            self.abort_in_background()
            raise

        if self.is_awaitable(result):

            async def await_result() -> WorkResult:
                try:
                    data = await result
                except Exception:
                    abort_result = self.abort()
                    if self.is_awaitable(abort_result):
                        await abort_result
                    raise
                return self.build_execution_group_result(delivery_groups, path, data)

            return await_result()

        return self.build_execution_group_result(
            delivery_groups, path, cast("dict[str, Any]", result)
        )

    def build_execution_group_result(
        self,
        delivery_groups: Sequence[DeliveryGroup],
        path: Path | None,
        data: dict[str, Any],
    ) -> WorkResult:
        """Build the result of a completed execution group."""
        errors = self.collected_errors.errors
        value = ExecutionGroupValue(
            delivery_groups,
            path.as_list() if path else [],
            data,
            list(errors) if errors else None,
        )
        return WorkResult(value, self.get_incremental_work())

    def get_incremental_work(self) -> Work:
        """Get the incremental work produced by this executor.

        When errors have been collected, execution groups and item streams
        whose position has been nulled via error propagation are aborted and
        filtered out before they reach the scheduler, cancelling work that is
        no longer being delivered.
        """
        groups, tasks, streams = self.groups, self.tasks, self.streams
        collected_errors = self.collected_errors

        if not collected_errors.errors:
            return Work(groups, tasks, streams)

        has_nulled_position = collected_errors.has_nulled_position
        cancellation_reason = RuntimeError(
            "Cancelled secondary to null within original result"
        )

        filtered_tasks: list[ExecutionGroup] = []
        for task in tasks:
            if has_nulled_position(task.path):
                self.settle_abort_result(task.computation.abort(cancellation_reason))
            else:
                filtered_tasks.append(task)

        filtered_streams: list[ItemStream] = []
        for stream in streams:
            if has_nulled_position(stream.path):
                self.settle_abort_result(stream.queue.abort(cancellation_reason))
            else:
                filtered_streams.append(stream)

        return Work(groups, filtered_tasks, filtered_streams)

    def settle_abort_result(self, abort_result: AwaitableOrValue[None]) -> None:
        """Settle the asynchronous part of an abort in the background."""
        if self.is_awaitable(abort_result):
            self.settle_in_background([abort_result])

    def get_new_delivery_group_map(
        self,
        new_defer_usages: Sequence[DeferUsage],
        delivery_group_map: DeliveryGroupMap | None,
        path: Path | None,
    ) -> tuple[list[DeliveryGroup], DeliveryGroupMap]:
        """Get the new delivery group map.

        Instantiates new DeliveryGroups for the given path, returning an
        updated map of DeferUsage objects to DeliveryGroups.

        Note: As defer directives may be used with operations returning lists,
        a DeferUsage object may correspond to many DeliveryGroups.
        """
        new_delivery_groups: list[DeliveryGroup] = []
        new_delivery_group_map: DeliveryGroupMap = RefMap(
            None if delivery_group_map is None else delivery_group_map.items()
        )

        # For each new DeferUsage object:
        for new_defer_usage in new_defer_usages:
            parent_defer_usage = new_defer_usage.parent_defer_usage

            parent = (
                None
                if parent_defer_usage is None
                else delivery_group_from_defer_usage(
                    parent_defer_usage, new_delivery_group_map
                )
            )

            # Instantiate the new delivery group.
            delivery_group = DeliveryGroup(path, new_defer_usage.label, parent)

            # Add it to the list of new delivery groups.
            new_delivery_groups.append(delivery_group)

            # Update the map.
            new_delivery_group_map[new_defer_usage] = delivery_group

        return new_delivery_groups, new_delivery_group_map

    def handle_stream(
        self,
        index: int,
        path: Path,
        iterator: Iterator[Any] | AsyncIterator[Any],
        is_async: bool,
        stream_usage: StreamUsage,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> bool:
        """Stream the remaining list items via an item stream."""
        queue = self.build_stream_item_queue(
            index,
            path,
            iterator,
            stream_usage.field_details_list,
            info,
            item_type,
            is_async,
        )

        item_stream = ItemStream(path, stream_usage.label, queue, index)

        self.streams.append(item_stream)
        return True

    def build_stream_item_queue(
        self,
        initial_index: int,
        stream_path: Path,
        iterator: Iterator[Any] | AsyncIterator[Any],
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        is_async: bool,
    ) -> StreamItemQueue:
        """Build the stream item queue for a streamed list field."""
        enable_early_execution = self.enable_early_execution
        is_awaitable = self.is_awaitable

        async def produce(queue: StreamItemQueue) -> None:
            index = initial_index
            while True:
                try:
                    item = (
                        await anext(cast("AsyncIterator[Any]", iterator))
                        if is_async
                        else next(cast("Iterator[Any]", iterator))
                    )
                except (StopAsyncIteration, StopIteration):
                    return
                except Exception as raw_error:
                    raise located_error(
                        raw_error, to_nodes(field_details_list), stream_path.as_list()
                    ) from raw_error

                item_path = stream_path.add_key(index, None)

                sub_executor = self.create_sub_executor()

                result = sub_executor.complete_stream_item(
                    item_path, item, field_details_list, info, item_type
                )
                if is_awaitable(result):
                    if enable_early_execution:
                        await queue.push(ensure_future(result))
                    else:
                        await queue.push(await result)
                else:
                    await queue.push(cast("WorkResult", result))

                index += 1

        def on_abort(_reason: BaseException | None) -> AwaitableOrValue[None]:
            if is_async:
                aclose = getattr(iterator, "aclose", None)
                if aclose is not None:

                    async def close_iterator() -> None:
                        with suppress_exceptions:
                            await aclose()

                    return close_iterator()
                return None
            # Drain the sync iterator so that any awaitable items it still
            # holds can be settled before they would be orphaned.
            self.track_async_work(
                collect_iterator_awaitables(
                    cast("Iterator[Any]", iterator), is_awaitable
                )
            )
            return None

        return StreamItemQueue(produce, on_abort, eager=enable_early_execution)

    def complete_stream_item(
        self,
        item_path: Path,
        item: Any,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> AwaitableOrValue[WorkResult]:
        """Complete a stream item on this sub-executor."""
        is_awaitable = self.is_awaitable
        if is_awaitable(item):

            async def await_stream_item_result() -> WorkResult:
                try:
                    completed = await self.complete_awaitable_value(
                        item_type,
                        field_details_list,
                        info,
                        item_path,
                        item,
                        None,
                    )
                except Exception:
                    abort_result = self.abort()
                    if is_awaitable(abort_result):
                        await abort_result
                    raise
                return self.build_stream_item_result(completed)

            return await_stream_item_result()

        try:
            try:
                completed = self.complete_value(
                    item_type,
                    field_details_list,
                    info,
                    item_path,
                    item,
                    None,
                )
            except Exception as raw_error:
                self.handle_field_error(
                    raw_error, item_type, field_details_list, item_path
                )
                return self.build_stream_item_result(None)
        except Exception:
            self.abort_in_background()
            raise

        if is_awaitable(completed):

            async def await_completed_stream_item_result() -> WorkResult:
                try:
                    try:
                        resolved = await completed
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error, item_type, field_details_list, item_path
                        )
                        resolved = None
                except Exception:
                    abort_result = self.abort()
                    if is_awaitable(abort_result):
                        await abort_result
                    raise
                return self.build_stream_item_result(resolved)

            return await_completed_stream_item_result()

        return self.build_stream_item_result(completed)

    def build_stream_item_result(self, item: Any) -> WorkResult:
        """Build the result of a completed stream item."""
        errors = self.collected_errors.errors
        value = StreamItemValue(item, list(errors) if errors else None)
        return WorkResult(value, self.get_incremental_work())


def should_defer(
    parent_defer_usages: DeferUsageSet | None, defer_usage_set: DeferUsageSet
) -> bool:
    """Decide whether to defer the given defer usage set.

    If we have a new child defer usage, defer.
    Otherwise, this defer usage was already deferred when it was initially
    encountered, and is now in the midst of executing early, so the new
    deferred grouped fields set can be executed immediately.
    """
    return parent_defer_usages is None or not all(
        defer_usage in parent_defer_usages for defer_usage in defer_usage_set
    )


def get_delivery_groups(
    defer_usage_set: DeferUsageSet, delivery_group_map: DeliveryGroupMap
) -> list[DeliveryGroup]:
    """Get the delivery groups for the given defer usages."""
    return [
        delivery_group_from_defer_usage(defer_usage, delivery_group_map)
        for defer_usage in defer_usage_set
    ]


def delivery_group_from_defer_usage(
    defer_usage: DeferUsage, delivery_group_map: DeliveryGroupMap
) -> DeliveryGroup:
    """Get the delivery group mapped to the given defer usage."""
    return delivery_group_map[defer_usage]
