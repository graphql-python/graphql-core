"""Incremental Publisher"""

from __future__ import annotations

from asyncio import Event, Task, ensure_future, gather
from contextlib import suppress
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Sequence,
    cast,
)

from graphql.execution.types import (
    CompletedResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalDeferResult,
    IncrementalStreamResult,
    InitialIncrementalExecutionResult,
    PendingResult,
    SubsequentIncrementalExecutionResult,
    is_cancellable_stream_record,
    is_deferred_fragment_record,
    is_deferred_grouped_field_set_record,
    is_deferred_grouped_field_set_result,
    is_non_reconcilable_deferred_grouped_field_set_result,
)

from ..pyutils.is_awaitable import is_awaitable

try:
    from typing import Protocol
except ImportError:  # Python < 3.8
    from typing_extensions import Protocol

if TYPE_CHECKING:
    from graphql.execution.types import (
        CancellableStreamRecord,
        DeferredFragmentRecord,
        DeferredGroupedFieldSetResult,
        IncrementalDataRecord,
        IncrementalDataRecordResult,
        IncrementalResult,
        ReconcilableDeferredGroupedFieldSetResult,
        StreamItemsRecord,
        StreamItemsResult,
        SubsequentResultRecord,
    )

    from ..error import GraphQLError


__all__ = [
    "IncrementalPublisher",
    "IncrementalPublisherContext",
    "build_incremental_response",
]

suppress_key_error = suppress(KeyError)


class IncrementalPublisherContext(Protocol):
    """The context for incremental publishing."""

    cancellable_streams: set[CancellableStreamRecord] | None


class IncrementalPublisher:
    """Publish incremental results.

    This class is used to publish incremental results to the client, enabling
    semi-concurrent execution while preserving result order.

    For internal use only.
    """

    _context: IncrementalPublisherContext
    _next_id: int
    _pending: dict[SubsequentResultRecord, None]
    _completed_result_queue: list[IncrementalDataRecordResult]
    _new_pending: dict[SubsequentResultRecord, None]
    _incremental: list[IncrementalResult]
    _completed: list[CompletedResult]

    _resolve: Event | None
    _tasks: set[Task[Any]]

    def __init__(self, context: IncrementalPublisherContext) -> None:
        self._context = context
        self._next_id = 0
        self._pending = {}
        self._completed_result_queue = []
        self._new_pending = {}
        self._incremental = []
        self._completed = []
        self._resolve = None  # lazy initialization
        self._tasks = set()

    def build_response(
        self,
        data: dict[str, Any],
        errors: list[GraphQLError] | None,
        incremental_data_records: Sequence[IncrementalDataRecord],
    ) -> ExperimentalIncrementalExecutionResults:
        """Build response."""
        self._add_incremental_data_records(incremental_data_records)
        self._prune_empty()

        pending = self._pending_sources_to_results()

        initial_result = InitialIncrementalExecutionResult(
            data,
            errors or None,
            pending=pending,
            has_next=True,
        )

        return ExperimentalIncrementalExecutionResults(
            initial_result, self._subscribe()
        )

    def _add_incremental_data_records(
        self, incremental_data_records: Sequence[IncrementalDataRecord]
    ) -> None:
        """Add incremental data records."""
        for incremental_data_record in incremental_data_records:
            if is_deferred_grouped_field_set_record(incremental_data_record):
                for (
                    deferred_fragment_record
                ) in incremental_data_record.deferred_fragment_records:
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
                    self._enqueue_completed_stream_items(await stream_result)

                self._add_task(enqueue_stream(stream_result))
            else:
                self._enqueue_completed_stream_items(stream_result)  # type: ignore

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

    def _prune_empty(self) -> None:
        """Prune empty."""
        maybe_empty_new_pending = self._new_pending
        self._new_pending = {}
        for node in maybe_empty_new_pending:
            if is_deferred_fragment_record(node):
                if node.expected_reconcilable_results:
                    self._new_pending[node] = None
                    continue
                for child in node.children:
                    self._add_non_empty_new_pending(child)
            else:
                self._new_pending[node] = None

    def _add_non_empty_new_pending(
        self, deferred_fragment_record: DeferredFragmentRecord
    ) -> None:
        """Add non-empty new pending."""
        if deferred_fragment_record.expected_reconcilable_results:
            self._new_pending[deferred_fragment_record] = None
            return
        for child in deferred_fragment_record.children:  # pragma: no cover
            self._add_non_empty_new_pending(child)

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
            self._completed_result_queue.append(result)
            self._trigger()

    def _enqueue_completed_stream_items(self, result: StreamItemsResult) -> None:
        """Enqueue completed stream items result."""
        self._completed_result_queue.append(result)
        self._trigger()

    def _pending_sources_to_results(self) -> list[PendingResult]:
        """Convert pending sources to pending results."""
        pending_results: list[PendingResult] = []
        for pending_source in self._new_pending:
            id_ = self._get_next_id()
            self._pending[pending_source] = None
            pending_source.id = id_
            path = pending_source.path
            label = pending_source.label
            pending_results.append(
                PendingResult(id_, path.as_list() if path else [], label)
            )
        self._new_pending.clear()
        return pending_results

    def _get_next_id(self) -> str:
        """Get the next ID for pending results."""
        id_ = self._next_id
        self._next_id += 1
        return str(id_)

    async def _subscribe(
        self,
    ) -> AsyncGenerator[SubsequentIncrementalExecutionResult, None]:
        """Subscribe to the incremental results."""
        try:
            is_done = False
            while not is_done:
                pending: list[PendingResult] = []

                completed_result_queue = self._completed_result_queue

                while completed_result_queue:
                    completed_result = completed_result_queue.pop(0)
                    if is_deferred_grouped_field_set_result(completed_result):
                        self._handle_completed_deferred_grouped_field_set(
                            completed_result
                        )
                    else:
                        completed_result = cast("StreamItemsResult", completed_result)
                        await self._handle_completed_stream_items(completed_result)

                    pending.extend(self._pending_sources_to_results())

                if self._incremental or self._completed:
                    has_next = bool(self._pending)

                    if not has_next:
                        is_done = True

                    subsequent_incremental_execution_result = (
                        SubsequentIncrementalExecutionResult(
                            has_next=has_next,
                            pending=pending or None,
                            incremental=self._incremental or None,
                            completed=self._completed or None,
                        )
                    )

                    self._incremental = []
                    self._completed = []

                    yield subsequent_incremental_execution_result

                else:
                    resolve = self._resolve
                    if resolve is None:
                        self._resolve = resolve = Event()
                    await resolve.wait()

        finally:
            await self._return_stream_iterators()

    async def _return_stream_iterators(self) -> None:
        """Finish all stream iterators."""
        cancellable_streams = self._context.cancellable_streams
        if cancellable_streams is None:
            return
        early_returns = [
            stream_record.early_return for stream_record in cancellable_streams
        ]
        if early_returns:
            await gather(*early_returns, return_exceptions=True)

    def _trigger(self) -> None:
        """Trigger the resolve event."""
        resolve = self._resolve
        if resolve is not None:
            resolve.set()
        self._resolve = Event()

    def _handle_completed_deferred_grouped_field_set(
        self, deferred_grouped_field_set_result: DeferredGroupedFieldSetResult
    ) -> None:
        """Handle completed deferred grouped field set result."""
        if is_non_reconcilable_deferred_grouped_field_set_result(
            deferred_grouped_field_set_result
        ):
            for (
                deferred_fragment_record
            ) in deferred_grouped_field_set_result.deferred_fragment_records:
                id_ = deferred_fragment_record.id
                if id_ is not None:  # pragma: no branch
                    self._completed.append(
                        CompletedResult(id_, deferred_grouped_field_set_result.errors)
                    )
                    del self._pending[deferred_fragment_record]
            return
        deferred_grouped_field_set_result = cast(
            "ReconcilableDeferredGroupedFieldSetResult",
            deferred_grouped_field_set_result,
        )
        for (
            deferred_fragment_record
        ) in deferred_grouped_field_set_result.deferred_fragment_records:
            deferred_fragment_record.reconcilable_results.append(
                deferred_grouped_field_set_result
            )
        incremental_data_records = (
            deferred_grouped_field_set_result.incremental_data_records
        )
        if incremental_data_records is not None:
            self._add_incremental_data_records(incremental_data_records)
        append_incremental = self._incremental.append
        for (
            deferred_fragment_record
        ) in deferred_grouped_field_set_result.deferred_fragment_records:
            id_ = deferred_fragment_record.id
            if id_ is None:
                continue  # pragma: no cover
            reconcilable_results = deferred_fragment_record.reconcilable_results
            if deferred_fragment_record.expected_reconcilable_results != len(
                reconcilable_results
            ):
                continue
            for reconcilable_result in reconcilable_results:
                if reconcilable_result.sent:
                    continue
                reconcilable_result.sent = True
                best_id, sub_path = self._get_best_id_and_sub_path(
                    id_, deferred_fragment_record, reconcilable_result
                )
                result = reconcilable_result.result
                incremental_entry = IncrementalDeferResult(
                    data=result.data,
                    id=best_id,
                    sub_path=sub_path,
                    errors=result.errors,
                )
                append_incremental(incremental_entry)
            self._completed.append(CompletedResult(id_))
            del self._pending[deferred_fragment_record]
            extend_completed = self._completed_result_queue.extend
            for child in deferred_fragment_record.children:
                self._new_pending[child] = None
                extend_completed(child.results)

        self._prune_empty()

    async def _handle_completed_stream_items(
        self, stream_items_result: StreamItemsResult
    ) -> None:
        """Handle completed stream."""
        stream_record = stream_items_result.stream_record
        id_ = stream_record.id
        if id_ is None:
            return  # pragma: no cover
        if stream_items_result.errors is not None:
            self._completed.append(CompletedResult(id_, stream_items_result.errors))
            del self._pending[stream_record]
            if is_cancellable_stream_record(stream_record):
                cancellable_streams = self._context.cancellable_streams
                if cancellable_streams:  # pragma: no branch
                    cancellable_streams.discard(stream_record)
                with suppress(Exception):
                    await stream_record.early_return
        elif stream_items_result.result is None:
            self._completed.append(CompletedResult(id_))
            del self._pending[stream_record]
            if is_cancellable_stream_record(stream_record):
                cancellable_streams = self._context.cancellable_streams
                if cancellable_streams:  # pragma: no branch
                    cancellable_streams.discard(stream_record)
        else:
            result = stream_items_result.result
            incremental_entry = IncrementalStreamResult(
                items=result.items, id=id_, errors=result.errors
            )
            self._incremental.append(incremental_entry)
            if stream_items_result.incremental_data_records:  # pragma: no branch
                self._add_incremental_data_records(
                    stream_items_result.incremental_data_records
                )
                self._prune_empty()

    def _get_best_id_and_sub_path(
        self,
        initial_id: str,
        initial_deferred_fragment_record: DeferredFragmentRecord,
        deferred_grouped_field_set_result: DeferredGroupedFieldSetResult,
    ) -> tuple[str, list[str | int] | None]:
        """Get the best ID and sub path for the deferred grouped field set result."""
        path = initial_deferred_fragment_record.path
        max_length = len(path.as_list()) if path else 0
        best_id = initial_id
        for (
            deferred_fragment_record
        ) in deferred_grouped_field_set_result.deferred_fragment_records:
            if deferred_fragment_record is initial_deferred_fragment_record:
                continue
            id_ = deferred_fragment_record.id
            if id_ is None:
                continue  # pragma: no cover
            fragment_path = deferred_fragment_record.path
            length = len(fragment_path.as_list()) if fragment_path else 0
            if length > max_length:
                max_length = length
                best_id = id_
        sub_path = deferred_grouped_field_set_result.path[max_length:]
        return (best_id, sub_path or None)

    def _add_task(self, awaitable: Awaitable[Any]) -> None:
        """Add the given task to the tasks set for later execution."""
        tasks = self._tasks
        task = ensure_future(awaitable)
        tasks.add(task)
        task.add_done_callback(tasks.discard)


def build_incremental_response(
    context: IncrementalPublisherContext,
    result: dict[str, Any],
    errors: list[GraphQLError] | None,
    incremental_data_records: Sequence[IncrementalDataRecord],
) -> ExperimentalIncrementalExecutionResults:
    """Build an incremental response."""
    incremental_publisher = IncrementalPublisher(context)
    return incremental_publisher.build_response(
        result, errors, incremental_data_records
    )
