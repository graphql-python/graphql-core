"""Incremental Publisher"""

from __future__ import annotations

from asyncio import gather, sleep
from contextlib import suppress
from typing import (
    TYPE_CHECKING,
    Any,
    NamedTuple,
    cast,
)

from .incremental_graph import IncrementalGraph
from .types import (
    CompletedResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalDeferResult,
    IncrementalStreamResult,
    InitialIncrementalExecutionResult,
    PendingResult,
    SubsequentIncrementalExecutionResult,
    is_cancellable_stream_record,
    is_deferred_grouped_field_set_result,
    is_non_reconcilable_deferred_grouped_field_set_result,
)

try:
    from typing import Protocol
except ImportError:  # Python < 3.8
    from typing_extensions import Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from ..error import GraphQLError
    from .types import (
        CancellableStreamRecord,
        DeferredFragmentRecord,
        DeferredGroupedFieldSetResult,
        IncrementalDataRecord,
        IncrementalDataRecordResult,
        IncrementalResult,
        ReconcilableDeferredGroupedFieldSetResult,
        StreamItemsResult,
        SubsequentResultRecord,
    )

__all__ = [
    "IncrementalPublisher",
    "IncrementalPublisherContext",
    "build_incremental_response",
]

suppress_key_error = suppress(KeyError)


class IncrementalPublisherContext(Protocol):
    """The context for incremental publishing."""

    cancellable_streams: set[CancellableStreamRecord] | None


class SubsequentIncrementalExecutionResultContext(NamedTuple):
    """The context for subsequent incremental execution results."""

    pending: list[PendingResult]
    incremental: list[IncrementalResult]
    completed: list[CompletedResult]


class IncrementalPublisher:
    """Publish incremental results.

    This class is used to publish incremental results to the client, enabling
    semi-concurrent execution while preserving result order.

    For internal use only.
    """

    _context: IncrementalPublisherContext
    _next_id: int
    _incremental_graph: IncrementalGraph

    def __init__(self, context: IncrementalPublisherContext) -> None:
        self._context = context
        self._next_id = 0
        self._incremental_graph = IncrementalGraph()

    def build_response(
        self,
        data: dict[str, Any],
        errors: list[GraphQLError] | None,
        incremental_data_records: Sequence[IncrementalDataRecord],
    ) -> ExperimentalIncrementalExecutionResults:
        """Build response."""
        incremental_graph = self._incremental_graph
        incremental_graph.add_incremental_data_records(incremental_data_records)
        new_pending = incremental_graph.get_new_pending()

        pending = self._pending_sources_to_results(new_pending)

        initial_result = InitialIncrementalExecutionResult(
            data,
            errors or None,
            pending=pending,
            has_next=True,
        )

        return ExperimentalIncrementalExecutionResults(
            initial_result, self._subscribe()
        )

    def _pending_sources_to_results(
        self, new_pending: list[SubsequentResultRecord]
    ) -> list[PendingResult]:
        """Convert pending sources to pending results."""
        pending_results: list[PendingResult] = []
        for pending_source in new_pending:
            id_ = self._get_next_id()
            pending_source.id = id_
            path = pending_source.path
            label = pending_source.label
            pending_results.append(
                PendingResult(id_, path.as_list() if path else [], label)
            )
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
        incremental_graph = self._incremental_graph
        check_has_next = incremental_graph.has_next
        handle_completed_incremental_data = self._handle_completed_incremental_data
        completed_incremental_data = incremental_graph.completed_incremental_data()
        # use the raw iterator rather than 'async for' so as not to end the iterator
        # when exiting the loop with the next value
        get_next_results = completed_incremental_data.__aiter__().__anext__
        is_done = False
        try:
            while not is_done:
                try:
                    completed_results = await get_next_results()
                except StopAsyncIteration:  # pragma: no cover
                    break

                context = SubsequentIncrementalExecutionResultContext([], [], [])
                for completed_result in completed_results:
                    await handle_completed_incremental_data(completed_result, context)

                if context.incremental or context.completed:  # pragma: no branch
                    has_next = check_has_next()

                    if not has_next:
                        is_done = True

                    subsequent_incremental_execution_result = (
                        SubsequentIncrementalExecutionResult(
                            has_next=has_next,
                            pending=context.pending or None,
                            incremental=context.incremental or None,
                            completed=context.completed or None,
                        )
                    )

                    yield subsequent_incremental_execution_result
        finally:
            await self._stop_async_iterators()

    async def _stop_async_iterators(self) -> None:
        """Finish all async iterators."""
        self._incremental_graph.stop_incremental_data()
        cancellable_streams = self._context.cancellable_streams
        if cancellable_streams is None:
            return
        early_returns = [
            stream_record.early_return for stream_record in cancellable_streams
        ]
        if early_returns:
            await gather(*early_returns, return_exceptions=True)

    async def _handle_completed_incremental_data(
        self,
        completed_incremental_data: IncrementalDataRecordResult,
        context: SubsequentIncrementalExecutionResultContext,
    ) -> None:
        """Handle completed incremental data."""
        if is_deferred_grouped_field_set_result(completed_incremental_data):
            self._handle_completed_deferred_grouped_field_set(
                completed_incremental_data, context
            )
        else:
            completed_incremental_data = cast(
                "StreamItemsResult", completed_incremental_data
            )
            await self._handle_completed_stream_items(
                completed_incremental_data, context
            )
        new_pending = self._incremental_graph.get_new_pending()
        context.pending.extend(self._pending_sources_to_results(new_pending))

    def _handle_completed_deferred_grouped_field_set(
        self,
        deferred_grouped_field_set_result: DeferredGroupedFieldSetResult,
        context: SubsequentIncrementalExecutionResultContext,
    ) -> None:
        """Handle completed deferred grouped field set result."""
        append_completed = context.completed.append
        append_incremental = context.incremental.append
        record = deferred_grouped_field_set_result.deferred_grouped_field_set_record
        if is_non_reconcilable_deferred_grouped_field_set_result(
            deferred_grouped_field_set_result
        ):
            remove_deferred = self._incremental_graph.remove_deferred_fragment
            for deferred_fragment_record in record.deferred_fragment_records:
                if not remove_deferred(deferred_fragment_record):
                    # multiple deferred grouped field sets could error for a fragment
                    continue
                id_ = deferred_fragment_record.id
                if id_ is None:  # pragma: no cover
                    msg = "Missing deferred fragment record identifier."
                    raise RuntimeError(msg)
                append_completed(
                    CompletedResult(id_, deferred_grouped_field_set_result.errors)
                )
            return

        deferred_grouped_field_set_result = cast(
            "ReconcilableDeferredGroupedFieldSetResult",
            deferred_grouped_field_set_result,
        )
        self._incremental_graph.add_completed_reconcilable_deferred_grouped_field_set(
            deferred_grouped_field_set_result
        )
        incremental_data_records = (
            deferred_grouped_field_set_result.incremental_data_records
        )
        if incremental_data_records:
            self._incremental_graph.add_incremental_data_records(
                incremental_data_records
            )

        complete_deferred = self._incremental_graph.complete_deferred_fragment
        for deferred_fragment_record in record.deferred_fragment_records:
            reconcilable_results = complete_deferred(deferred_fragment_record)
            if reconcilable_results is None:
                continue
            id_ = deferred_fragment_record.id
            if id_ is None:  # pragma: no cover
                msg = "Missing deferred fragment record identifier."
                raise RuntimeError(msg)
            for reconcilable_result in reconcilable_results:
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
            append_completed(CompletedResult(id_))

    async def _handle_completed_stream_items(
        self,
        stream_items_result: StreamItemsResult,
        context: SubsequentIncrementalExecutionResultContext,
    ) -> None:
        """Handle completed stream."""
        stream_record = stream_items_result.stream_record
        id_ = stream_record.id
        if id_ is None:  # pragma: no cover
            msg = "Missing stream record identifier."
            raise RuntimeError(msg)
        incremental_graph = self._incremental_graph
        if stream_items_result.errors is not None:
            context.completed.append(CompletedResult(id_, stream_items_result.errors))
            incremental_graph.remove_stream(stream_record)
            if is_cancellable_stream_record(stream_record):
                cancellable_streams = self._context.cancellable_streams
                if cancellable_streams:  # pragma: no branch
                    cancellable_streams.discard(stream_record)
                with suppress(Exception):
                    await stream_record.early_return
        elif stream_items_result.result is None:
            context.completed.append(CompletedResult(id_))
            incremental_graph.remove_stream(stream_record)
            if is_cancellable_stream_record(stream_record):
                cancellable_streams = self._context.cancellable_streams
                if cancellable_streams:  # pragma: no branch
                    cancellable_streams.discard(stream_record)
        else:
            result = stream_items_result.result
            incremental_entry = IncrementalStreamResult(
                items=result.items, id=id_, errors=result.errors
            )
            context.incremental.append(incremental_entry)
            incremental_data_records = stream_items_result.incremental_data_records
            if incremental_data_records is not None:  # pragma: no branch
                incremental_graph.add_incremental_data_records(incremental_data_records)
                await sleep(0)  # allow other tasks to run

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
        record = deferred_grouped_field_set_result.deferred_grouped_field_set_record
        for deferred_fragment_record in record.deferred_fragment_records:
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
