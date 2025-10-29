"""Incremental Graphs."""

from __future__ import annotations

from asyncio import CancelledError, Future, Task, ensure_future
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Generator,
    Iterable,
    Sequence,
    cast,
)

from graphql.execution.types import (
    is_deferred_fragment_record,
    is_deferred_grouped_field_set_record,
)

from ..pyutils.is_awaitable import is_awaitable

if TYPE_CHECKING:
    from graphql.execution.types import (
        DeferredFragmentRecord,
        DeferredGroupedFieldSetResult,
        IncrementalDataRecord,
        IncrementalDataRecordResult,
        ReconcilableDeferredGroupedFieldSetResult,
        StreamItemsRecord,
        StreamItemsResult,
        SubsequentResultRecord,
    )

__all__ = ["IncrementalGraph"]


class IncrementalGraph:
    """Helper class to execute incremental Graphs.

    For internal use only.
    """

    _pending: dict[SubsequentResultRecord, None]
    _new_pending: dict[SubsequentResultRecord, None]
    _completed_queue: list[IncrementalDataRecordResult]
    _next_queue: list[Future[Iterable[IncrementalDataRecordResult]]]

    _tasks: set[Task[Any]]  # benutzt????

    def __init__(self) -> None:
        """Initialize the IncrementalGraph."""
        self._pending = {}
        self._new_pending = {}
        self._completed_queue = []
        self._next_queue = []
        self._tasks = set()

    def add_incremental_data_records(
        self, incremental_data_records: Sequence[IncrementalDataRecord]
    ) -> None:
        """Add incremental data records."""
        for incremental_data_record in incremental_data_records:
            if is_deferred_grouped_field_set_record(incremental_data_record):
                for deferred_fragment_record in (
                    incremental_data_record.deferred_fragment_records
                ):  # pragma: no branch
                    deferred_fragment_record.expected_reconcilable_results += 1
                    self._add_deferred_fragment_record(deferred_fragment_record)

                deferred_result = incremental_data_record.result
                if is_awaitable(deferred_result):

                    async def enqueue_deferred(
                        deferred_result: Awaitable[DeferredGroupedFieldSetResult],
                    ) -> None:
                        self._enqueue_completed_deferred_grouped_field_set(
                            await deferred_result
                        )

                    self._add_task(enqueue_deferred(deferred_result))
                else:
                    self._enqueue_completed_deferred_grouped_field_set(
                        deferred_result,  # type: ignore
                    )
                continue

            incremental_data_record = cast("StreamItemsRecord", incremental_data_record)
            stream_record = incremental_data_record.stream_record
            if stream_record.id is None:
                self._new_pending[stream_record] = None

            stream_result = incremental_data_record.result
            if is_awaitable(stream_result):

                async def enqueue_stream(
                    stream_result: Awaitable[StreamItemsResult],
                ) -> None:
                    self._enqueue(await stream_result)

                self._add_task(enqueue_stream(stream_result))
            else:
                self._enqueue(stream_result)  # type: ignore

    def get_new_pending(self) -> list[SubsequentResultRecord]:
        """Get new pending subsequent result records."""
        maybe_empty_new_pending = self._new_pending
        pending = self._pending
        add_non_empty_new_pending = self._add_non_empty_new_pending
        new_pending: list[SubsequentResultRecord] = []
        append_new_pending = new_pending.append
        for node in maybe_empty_new_pending:
            if is_deferred_fragment_record(node):
                if node.expected_reconcilable_results:
                    pending[node] = None
                    append_new_pending(node)
                    continue
                for child in node.children:
                    add_non_empty_new_pending(child, new_pending)
            else:
                pending[node] = None
                append_new_pending(node)
        self._new_pending.clear()
        return new_pending

    async def completed_incremental_data(
        self,
    ) -> AsyncGenerator[Iterable[IncrementalDataRecordResult], None]:
        """Asynchronously yield completed incremental data record results."""
        while True:
            if self._completed_queue:
                first_result = self._completed_queue.pop(0)
                yield self._yield_current_completed_incremental_data(first_result)
            else:
                future: Future[Iterable[IncrementalDataRecordResult]] = Future()
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
        reconcilable_results = deferred_fragment_record.reconcilable_results
        if deferred_fragment_record.expected_reconcilable_results != len(
            reconcilable_results
        ):
            return None
        self.remove_subsequent_result_record(deferred_fragment_record)
        new_pending = self._new_pending
        for child in deferred_fragment_record.children:
            new_pending[child] = None
            for result in child.results:
                self._enqueue(result)
        return reconcilable_results

    def remove_subsequent_result_record(
        self,
        subsequent_result_record: SubsequentResultRecord,
    ) -> None:
        """Remove a subsequent result record as no longer pending."""
        del self._pending[subsequent_result_record]
        if not self._pending:
            self.stop_incremental_data()

    def _add_deferred_fragment_record(
        self, deferred_fragment_record: DeferredFragmentRecord
    ) -> None:
        """Add deferred fragment record."""
        parent = deferred_fragment_record.parent
        if parent is None:
            if deferred_fragment_record.id is not None:
                return
            self._new_pending[deferred_fragment_record] = None
            return
        if deferred_fragment_record in parent.children:
            return
        parent.children[deferred_fragment_record] = None
        self._add_deferred_fragment_record(parent)

    def _add_non_empty_new_pending(
        self,
        deferred_fragment_record: DeferredFragmentRecord,
        new_pending: list[SubsequentResultRecord],
    ) -> None:
        """Add non-empty new pending deferred fragment record."""
        if deferred_fragment_record.expected_reconcilable_results:
            self._pending[deferred_fragment_record] = None
            new_pending.append(deferred_fragment_record)
            return
        add = self._add_non_empty_new_pending  # pragma: no cover
        for child in deferred_fragment_record.children:  # pragma: no cover
            add(child, new_pending)

    def _enqueue_completed_deferred_grouped_field_set(
        self, result: DeferredGroupedFieldSetResult
    ) -> None:
        """Enqueue completed deferred grouped field set result."""
        has_pending_parent = False
        for deferred_fragment_record in result.deferred_fragment_records:
            if deferred_fragment_record.id is not None:
                has_pending_parent = True
            deferred_fragment_record.results.append(result)
        if has_pending_parent:
            self._enqueue(result)

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
