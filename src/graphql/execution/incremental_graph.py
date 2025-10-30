"""Incremental Graphs."""

from __future__ import annotations

from asyncio import (
    CancelledError,
    Future,
    Task,
    ensure_future,
    get_running_loop,
    isfuture,
)
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Generator,
    Iterable,
    Sequence,
    Union,
    cast,
)

from graphql.execution.types import (
    StreamRecord,
    is_deferred_grouped_field_set_record,
)

if TYPE_CHECKING:
    from graphql.execution.types import (
        DeferredFragmentRecord,
        DeferredGroupedFieldSetRecord,
        IncrementalDataRecord,
        IncrementalDataRecordResult,
        ReconcilableDeferredGroupedFieldSetResult,
        StreamItemsRecord,
        SubsequentResultRecord,
    )

    try:
        from typing import TypeGuard
    except ImportError:  # Python < 3.10
        from typing_extensions import TypeGuard

__all__ = ["IncrementalGraph"]


class DeferredFragmentNode:
    """A node representing a deferred fragment in the incremental graph."""

    __slots__ = (
        "children",
        "deferred_fragment_record",
        "deferred_grouped_field_set_records",
        "reconcilable_results",
    )

    deferred_fragment_record: DeferredFragmentRecord
    deferred_grouped_field_set_records: dict[DeferredGroupedFieldSetRecord, None]
    reconcilable_results: dict[ReconcilableDeferredGroupedFieldSetResult, None]
    children: list[DeferredFragmentNode]

    def __init__(self, deferred_fragment_record: DeferredFragmentRecord) -> None:
        """Initialize the DeferredFragmentNode."""
        self.deferred_fragment_record = deferred_fragment_record
        self.deferred_grouped_field_set_records = {}
        self.reconcilable_results = {}
        self.children = []


SubsequentResultNode = Union[DeferredFragmentNode, StreamRecord]


def is_deferred_fragment_node(
    node: DeferredFragmentNode | None,
) -> TypeGuard[DeferredFragmentNode]:
    """Check whether the given node is a deferred fragment node."""
    return isinstance(node, DeferredFragmentNode)


def is_stream_node(
    node: SubsequentResultNode | None,
) -> TypeGuard[StreamRecord]:
    """Check whether the given result node is a stream node."""
    return isinstance(node, StreamRecord)


class IncrementalGraph:
    """Helper class to execute incremental Graphs.

    For internal use only.
    """

    _pending: dict[SubsequentResultNode, None]
    _deferred_fragment_nodes: dict[DeferredFragmentRecord, DeferredFragmentNode]
    _new_pending: dict[SubsequentResultNode, None]
    _new_incremental_data_records: dict[IncrementalDataRecord, None]
    _completed_queue: list[IncrementalDataRecordResult]
    _next_queue: list[Future[Iterable[IncrementalDataRecordResult]]]

    _tasks: set[Task[Any]]  # benutzt????

    def __init__(self) -> None:
        """Initialize the IncrementalGraph."""
        self._pending = {}
        self._deferred_fragment_nodes = {}
        self._new_pending = {}
        self._new_incremental_data_records = {}
        self._completed_queue = []
        self._next_queue = []
        self._tasks = set()

    def add_incremental_data_records(
        self, incremental_data_records: Sequence[IncrementalDataRecord]
    ) -> None:
        """Add incremental data records."""
        for incremental_data_record in incremental_data_records:
            if is_deferred_grouped_field_set_record(incremental_data_record):
                self._add_deferred_grouped_field_set_record(incremental_data_record)
            else:
                stream_items_record = cast("StreamItemsRecord", incremental_data_record)
                self._add_stream_items_record(stream_items_record)

    def add_completed_reconcilable_deferred_grouped_field_set(
        self, reconcilable_result: ReconcilableDeferredGroupedFieldSetResult
    ) -> None:
        """Add a completed reconcilable deferred grouped field set result."""
        record = reconcilable_result.deferred_grouped_field_set_record
        deferred_fragment_nodes = filter(
            is_deferred_fragment_node,
            map(
                self._deferred_fragment_nodes.get,
                record.deferred_fragment_records,
            ),
        )
        for deferred_fragment_node in deferred_fragment_nodes:
            del deferred_fragment_node.deferred_grouped_field_set_records[record]
            deferred_fragment_node.reconcilable_results[reconcilable_result] = None

    def get_new_pending(self) -> list[SubsequentResultRecord]:
        """Get new pending subsequent result records."""
        _pending, _new_pending = self._pending, self._new_pending
        _new_incremental_data_records = self._new_incremental_data_records
        new_pending: list[SubsequentResultRecord] = []
        add_result = new_pending.append
        # avoid iterating over a changing dict
        iterate = list(_new_pending)
        add_iteration = iterate.append
        while iterate:
            node = iterate.pop(0)
            if is_stream_node(node):
                _pending[node] = None
                add_result(node)
            elif node.deferred_grouped_field_set_records:  # type: ignore
                records = node.deferred_grouped_field_set_records  # type: ignore
                for deferred_grouped_field_set_node in records:  # pragma: no branch
                    _new_incremental_data_records[deferred_grouped_field_set_node] = (
                        None
                    )
                _pending[node] = None
                add_result(node.deferred_fragment_record)  # type: ignore
            else:
                for child in node.children:  # type: ignore
                    _new_pending[child] = None
                    add_iteration(child)
        _new_pending.clear()

        enqueue = self._enqueue
        for incremental_data_record in _new_incremental_data_records:
            value = incremental_data_record.result.value
            if isfuture(value):

                async def enqueue_later(
                    value: Awaitable[IncrementalDataRecordResult],
                ) -> None:
                    enqueue(await value)

                self._add_task(enqueue_later(value))
            else:
                enqueue(value)
        _new_incremental_data_records.clear()

        return new_pending

    async def completed_incremental_data(
        self,
    ) -> AsyncGenerator[Iterable[IncrementalDataRecordResult], None]:
        """Asynchronously yield completed incremental data record results."""
        loop = get_running_loop()
        while True:
            if self._completed_queue:
                first_result = self._completed_queue.pop(0)
                yield self._yield_current_completed_incremental_data(first_result)
            else:
                future: Future[Iterable[IncrementalDataRecordResult]] = (
                    loop.create_future()
                )
                self._next_queue.append(future)
                try:
                    yield await future
                except CancelledError:
                    break  # pragma: no cover

    def has_next(self) -> bool:
        """Check if there are more results to process."""
        return bool(self._pending)

    def complete_deferred_fragment(
        self,
        deferred_fragment_record: DeferredFragmentRecord,
    ) -> list[ReconcilableDeferredGroupedFieldSetResult] | None:
        """Complete a deferred fragment."""
        deferred_fragment_nodes = self._deferred_fragment_nodes
        try:
            deferred_fragment_node = deferred_fragment_nodes[deferred_fragment_record]
        except KeyError:  # pragma: no cover
            return None
        if deferred_fragment_node.deferred_grouped_field_set_records:
            return None
        reconcilable_results = list(deferred_fragment_node.reconcilable_results)
        for reconcilable_result in reconcilable_results:
            record = reconcilable_result.deferred_grouped_field_set_record
            for other_deferred_fragment_record in record.deferred_fragment_records:
                try:
                    other_deferred_fragment_node = deferred_fragment_nodes[
                        other_deferred_fragment_record
                    ]
                except KeyError:  # pragma: no cover
                    continue
                del other_deferred_fragment_node.reconcilable_results[
                    reconcilable_result
                ]
        self._remove_pending(deferred_fragment_node)
        new_pending = self._new_pending
        for child in deferred_fragment_node.children:
            new_pending[child] = None
        return reconcilable_results

    def remove_deferred_fragment(
        self,
        deferred_fragment_record: DeferredFragmentRecord,
    ) -> bool:
        """Check if deferred fragment exists and remove it in that case."""
        deferred_fragment_nodes = self._deferred_fragment_nodes
        try:
            deferred_fragment_node = deferred_fragment_nodes[deferred_fragment_record]
        except KeyError:  # pragma: no cover
            return False
        self._remove_pending(deferred_fragment_node)
        del deferred_fragment_nodes[deferred_fragment_record]
        for child in deferred_fragment_node.children:  # pragma: no cover
            self.remove_deferred_fragment(child.deferred_fragment_record)
        return True

    def remove_stream(self, stream_record: StreamRecord) -> None:
        """Remove a stream record as no longer pending."""
        self._remove_pending(stream_record)

    def _remove_pending(self, subsequent_result_node: SubsequentResultNode) -> None:
        """Remove a subsequent result node as no longer pending."""
        del self._pending[subsequent_result_node]
        if not self._pending:
            self.stop_incremental_data()

    def _add_deferred_grouped_field_set_record(
        self, deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord
    ) -> None:
        """Add a deferred grouped field set record."""
        pending = self._pending
        new_incremental_data_records = self._new_incremental_data_records
        add = self._add_deferred_fragment_node
        records = deferred_grouped_field_set_record.deferred_fragment_records
        for deferred_fragment_record in records:  # pragma: no branch
            deferred_fragment_node = add(deferred_fragment_record)
            if deferred_fragment_node in pending:
                new_incremental_data_records[deferred_grouped_field_set_record] = None
            deferred_fragment_node.deferred_grouped_field_set_records[
                deferred_grouped_field_set_record
            ] = None

    def _add_stream_items_record(self, stream_items_record: StreamItemsRecord) -> None:
        """Add a stream items record."""
        stream_record = stream_items_record.stream_record
        if stream_record not in self._pending:
            self._new_pending[stream_record] = None
        self._new_incremental_data_records[stream_items_record] = None

    def _add_deferred_fragment_node(
        self, deferred_fragment_record: DeferredFragmentRecord
    ) -> DeferredFragmentNode:
        """Add a deferred fragment node."""
        try:
            deferred_fragment_node = self._deferred_fragment_nodes[
                deferred_fragment_record
            ]
        except KeyError:
            deferred_fragment_node = DeferredFragmentNode(deferred_fragment_record)
            self._deferred_fragment_nodes[deferred_fragment_record] = (
                deferred_fragment_node
            )
            parent = deferred_fragment_record.parent
            if parent is None:
                self._new_pending[deferred_fragment_node] = None
            else:
                parent_node = self._add_deferred_fragment_node(parent)
                parent_node.children.append(deferred_fragment_node)
        return deferred_fragment_node

    def _add_task(self, awaitable: Awaitable[Any]) -> None:
        """Add the given task to the tasks set for later execution."""
        tasks = self._tasks
        task = ensure_future(awaitable)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def stop_incremental_data(self) -> None:
        """Stop the delivery of inclremental data."""
        for future in self._next_queue:
            future.cancel()  # pragma: no cover

    def _yield_current_completed_incremental_data(
        self, first_result: IncrementalDataRecordResult
    ) -> Generator[IncrementalDataRecordResult, None, None]:
        """Yield the current completed incremental data."""
        yield first_result
        queue = self._completed_queue
        while queue:
            yield queue.pop(0)

    def _enqueue(self, completed: IncrementalDataRecordResult) -> None:
        """Enqueue completed incremental data record result."""
        try:
            future = self._next_queue.pop(0)
        except IndexError:
            self._completed_queue.append(completed)
        else:
            future.set_result(self._yield_current_completed_incremental_data(completed))
