"""Incremental Graphs."""

from __future__ import annotations

from asyncio import (
    Future,
    Task,
    ensure_future,
    get_running_loop,
    isfuture,
    sleep,
)
from collections import deque
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from ..pyutils import BoxedAwaitableOrValue, Undefined, is_awaitable
from .types import (
    StreamItemsRecordResult,
    StreamItemsResult,
    StreamRecord,
    is_deferred_fragment_record,
    is_pending_execution_group,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Generator, Iterable, Sequence

    from ..error.graphql_error import GraphQLError
    from .types import (
        DeferredFragmentRecord,
        DeliveryGroup,
        IncrementalDataRecord,
        IncrementalDataRecordResult,
        PendingExecutionGroup,
        SuccessfulExecutionGroup,
    )

__all__ = ["IncrementalGraph"]


class IncrementalGraph:
    """Helper class to execute incremental Graphs.

    For internal use only.
    """

    _root_nodes: dict[DeliveryGroup, None]
    _completed_queue: list[IncrementalDataRecordResult]
    _next_queue: list[Future[Iterable[IncrementalDataRecordResult] | None]]

    _tasks: set[Task[Any]]

    def __init__(self) -> None:
        """Initialize the IncrementalGraph."""
        self._root_nodes = {}
        self._completed_queue = []
        self._next_queue = []
        self._tasks = set()

    def get_new_root_nodes(
        self, incremental_data_records: Sequence[IncrementalDataRecord]
    ) -> list[DeliveryGroup]:
        """Get new root nodes."""
        initial_result_children: dict[DeliveryGroup, None] = {}
        self._add_incremental_data_records(
            incremental_data_records, None, initial_result_children
        )
        return self._promote_non_empty_to_root(initial_result_children)

    def add_completed_successful_execution_group(
        self, successful_execution_group: SuccessfulExecutionGroup
    ) -> None:
        """Add a completed successful execution group."""
        pending_group = successful_execution_group.pending_execution_group
        deferred_records = pending_group.deferred_fragment_records
        for defererred_record in deferred_records:
            del defererred_record.pending_execution_groups[pending_group]
            defererred_record.successful_execution_groups[
                successful_execution_group
            ] = None

        incremental_data_records = successful_execution_group.incremental_data_records
        if incremental_data_records is not None:
            self._add_incremental_data_records(
                incremental_data_records, deferred_records
            )

    def current_completed_batch(
        self,
    ) -> Generator[IncrementalDataRecordResult, None, None]:
        """Yield the current completed batch of incremental data record results."""
        queue = self._completed_queue
        while queue:
            yield queue.pop(0)
        if not self._root_nodes:
            self.abort()

    def next_completed_batch(
        self,
    ) -> Future[Iterable[IncrementalDataRecordResult] | None]:
        """Return a future that resolves to the next completed batch."""
        loop = get_running_loop()
        future: Future[Iterable[IncrementalDataRecordResult] | None] = (
            loop.create_future()
        )
        self._next_queue.append(future)
        return future

    def abort(self) -> None:
        """Abort the incremental graph execution."""
        for resolve in self._next_queue:
            resolve.set_result(None)  # pragma: no cover

    def has_next(self) -> bool:
        """Check if there are more results to process."""
        return bool(self._root_nodes)

    def complete_deferred_fragment(
        self,
        deferred_fragment_record: DeferredFragmentRecord,
    ) -> (
        tuple[
            list[DeliveryGroup],
            list[SuccessfulExecutionGroup],
        ]
        | None
    ):
        """Complete a deferred fragment."""
        if (
            deferred_fragment_record not in self._root_nodes
            or deferred_fragment_record.pending_execution_groups
        ):
            return None
        successful_execution_groups = list(
            deferred_fragment_record.successful_execution_groups
        )
        self._remove_root_node(deferred_fragment_record)
        for successful_execution_group in successful_execution_groups:
            pending_execution_group = successful_execution_group.pending_execution_group
            deferred_records = pending_execution_group.deferred_fragment_records
            for other_deferred_fragment_record in deferred_records:
                with suppress(KeyError):
                    del other_deferred_fragment_record.successful_execution_groups[
                        successful_execution_group
                    ]
        new_root_nodes = self._promote_non_empty_to_root(
            deferred_fragment_record.children
        )
        return new_root_nodes, successful_execution_groups

    def remove_deferred_fragment(
        self,
        deferred_fragment_record: DeferredFragmentRecord,
    ) -> bool:
        """Check if deferred fragment exists and remove it in that case."""
        if deferred_fragment_record not in self._root_nodes:
            return False
        self._remove_root_node(deferred_fragment_record)
        return True

    def remove_stream(self, stream_record: StreamRecord) -> None:
        """Remove a stream record as no longer pending."""
        self._remove_root_node(stream_record)

    def stop_incremental_data(self) -> None:
        """Stop the delivery of incremental data."""
        for future in self._next_queue:
            future.cancel()  # pragma: no cover

    def _remove_root_node(self, delivery_group: DeliveryGroup) -> None:
        """Remove root node."""
        del self._root_nodes[delivery_group]

    def _add_incremental_data_records(
        self,
        incremental_data_records: Sequence[IncrementalDataRecord],
        parents: Sequence[DeferredFragmentRecord] | None = None,
        initial_result_children: dict[DeliveryGroup, None] | None = None,
    ) -> None:
        """Add incremental data records."""
        for incremental_data_record in incremental_data_records:
            if is_pending_execution_group(incremental_data_record):
                deferred_records = incremental_data_record.deferred_fragment_records
                for deferred_fragment_record in deferred_records:
                    self._add_deferred_fragment_node(
                        deferred_fragment_record, initial_result_children
                    )
                    deferred_fragment_record.pending_execution_groups[
                        incremental_data_record
                    ] = None
                if self._completes_root_node(incremental_data_record):
                    self._on_execution_group(incremental_data_record)
            elif parents is None:
                if initial_result_children is None:  # pragma: no cover
                    msg = "Invalid state while adding incremental data records."
                    raise RuntimeError(msg)
                initial_result_children[
                    cast("StreamRecord", incremental_data_record)
                ] = None
            else:
                for parent in parents:
                    self._add_deferred_fragment_node(parent, initial_result_children)
                    parent.children[cast("StreamRecord", incremental_data_record)] = (
                        None
                    )

    def _promote_non_empty_to_root(
        self, maybe_empty_new_root_nodes: dict[DeliveryGroup, None]
    ) -> list[DeliveryGroup]:
        """Promote non-empty nodes to root nodes."""
        new_root_nodes: list[DeliveryGroup] = []
        # use a deque to simulate how JavaScripts iterates over a changing set
        unprocessed_nodes = deque(maybe_empty_new_root_nodes)
        while unprocessed_nodes:
            node = unprocessed_nodes.popleft()
            if is_deferred_fragment_record(node):
                pending_execution_groups = node.pending_execution_groups
                if pending_execution_groups:
                    for pending_execution_group in pending_execution_groups:
                        if not self._completes_root_node(pending_execution_group):
                            self._on_execution_group(pending_execution_group)
                    self._root_nodes[node] = None
                    new_root_nodes.append(node)
                    continue
                for child in node.children:
                    if child not in maybe_empty_new_root_nodes:  # pragma: no branch
                        maybe_empty_new_root_nodes[cast("StreamRecord", child)] = None
                        unprocessed_nodes.append(child)
            else:
                self._root_nodes[node] = None
                new_root_nodes.append(cast("StreamRecord", node))
                self._add_task(self._on_stream_items(cast("StreamRecord", node)))
        return new_root_nodes

    def _completes_root_node(
        self, pending_execution_group: PendingExecutionGroup
    ) -> bool:
        """Check whether the given record completes a root node."""
        root_nodes = self._root_nodes
        deferred_records = pending_execution_group.deferred_fragment_records
        return any(record in root_nodes for record in deferred_records)

    def _add_deferred_fragment_node(
        self,
        deferred_fragment_record: DeferredFragmentRecord,
        initial_result_children: dict[DeliveryGroup, None] | None = None,
    ) -> None:
        """Add a deferred fragment node."""
        if deferred_fragment_record in self._root_nodes:
            return
        parent = deferred_fragment_record.parent
        if parent is None:
            if initial_result_children is None:  # pragma: no cover
                msg = "Invalid state while adding deferred fragment node."
                raise RuntimeError(msg)
            initial_result_children[deferred_fragment_record] = None
            return
        parent.children[deferred_fragment_record] = None
        self._add_deferred_fragment_node(parent, initial_result_children)

    def _on_execution_group(
        self, pending_execution_group: PendingExecutionGroup
    ) -> None:
        """Handle deferred grouped field set record."""
        completed_execution_group = pending_execution_group.result
        if not isinstance(completed_execution_group, BoxedAwaitableOrValue):
            completed_execution_group = completed_execution_group()
        value = completed_execution_group.value
        if is_awaitable(value):

            async def await_and_enqueue() -> None:
                self._enqueue(await value)

            self._add_task(await_and_enqueue())
        else:
            self._enqueue(value)

    async def _on_stream_items(self, stream_record: StreamRecord) -> None:
        """Handle stream items."""
        enqueue = self._enqueue
        items: list[Any] = []
        errors: list[GraphQLError] = []
        incremental_data_records: list[IncrementalDataRecord] = []
        stream_item_queue = stream_record.stream_item_queue
        while True:
            try:
                stream_item_record = stream_item_queue.pop(0)
            except IndexError:  # pragma: no cover
                break
            result = (
                stream_item_record.value
                if isinstance(stream_item_record, BoxedAwaitableOrValue)
                else stream_item_record().value
            )
            if isfuture(result):
                if items:
                    enqueue(
                        StreamItemsResult(
                            stream_record,
                            incremental_data_records,
                            StreamItemsRecordResult(items, errors or None),
                        )
                    )
                    items = []
                    errors = []
                    incremental_data_records = []
                await sleep(0)  # allow other tasks to run
                result = await result
            if result.item is Undefined:
                if items:
                    enqueue(
                        StreamItemsResult(
                            stream_record,
                            incremental_data_records,
                            StreamItemsRecordResult(items, errors or None),
                        )
                    )
                enqueue(StreamItemsResult(stream_record, errors=result.errors or None))
                return
            items.append(result.item)
            if result.errors:
                errors.extend(result.errors)
            if result.incremental_data_records:
                incremental_data_records.extend(result.incremental_data_records)

    def _yield_current_completed_incremental_data(
        self, first_result: IncrementalDataRecordResult
    ) -> Generator[IncrementalDataRecordResult, None, None]:
        """Yield the current completed incremental data."""
        yield first_result
        yield from self.current_completed_batch()

    def _enqueue(self, completed: IncrementalDataRecordResult) -> None:
        """Enqueue completed incremental data record result."""
        try:
            future = self._next_queue.pop(0)
        except IndexError:
            self._completed_queue.append(completed)
        else:
            future.set_result(self._yield_current_completed_incremental_data(completed))

    def _add_task(self, awaitable: Awaitable[Any]) -> None:
        """Add the given task to the tasks set for later execution."""
        tasks = self._tasks
        task = ensure_future(awaitable)
        tasks.add(task)
        task.add_done_callback(tasks.discard)
