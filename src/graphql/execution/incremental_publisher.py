"""Incremental Publisher"""

from __future__ import annotations

from asyncio import gather
from contextlib import suppress
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Sequence,
    cast,
)

from graphql.execution.incremental_graph import IncrementalGraph
from graphql.execution.types import (
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
    from graphql.execution.types import (
        CancellableStreamRecord,
        DeferredFragmentRecord,
        DeferredGroupedFieldSetResult,
        IncrementalDataRecord,
        IncrementalResult,
        ReconcilableDeferredGroupedFieldSetResult,
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
    _incremental_graph: IncrementalGraph
    _incremental: list[IncrementalResult]
    _completed: list[CompletedResult]

    def __init__(self, context: IncrementalPublisherContext) -> None:
        self._context = context
        self._next_id = 0
        self._incremental_graph = IncrementalGraph()
        self._incremental = []
        self._completed = []

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
        try:
            incremental_graph = self._incremental_graph
            completed_results = incremental_graph.completed_results
            get_new_pending = incremental_graph.get_new_pending
            new_result_available = incremental_graph.new_completed_result_available
            check_has_next = incremental_graph.has_next
            pending_sources_to_results = self._pending_sources_to_results
            is_done = False
            while not is_done:
                pending: list[PendingResult] = []

                for completed_result in completed_results():
                    if is_deferred_grouped_field_set_result(completed_result):
                        self._handle_completed_deferred_grouped_field_set(
                            completed_result
                        )
                    else:
                        completed_result = cast("StreamItemsResult", completed_result)
                        await self._handle_completed_stream_items(completed_result)

                    new_pending = get_new_pending()
                    pending.extend(pending_sources_to_results(new_pending))

                if self._incremental or self._completed:
                    has_next = check_has_next()

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
                    await new_result_available()

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

    def _handle_completed_deferred_grouped_field_set(
        self, deferred_grouped_field_set_result: DeferredGroupedFieldSetResult
    ) -> None:
        """Handle completed deferred grouped field set result."""
        append_completed = self._completed.append
        append_incremental = self._incremental.append
        if is_non_reconcilable_deferred_grouped_field_set_result(
            deferred_grouped_field_set_result
        ):
            remove_subsequent = self._incremental_graph.remove_subsequent_result_record
            for deferred_fragment_record in (
                deferred_grouped_field_set_result.deferred_fragment_records
            ):  # pragma: no branch
                id_ = deferred_fragment_record.id
                if id_ is not None:  # pragma: no branch
                    append_completed(
                        CompletedResult(id_, deferred_grouped_field_set_result.errors)
                    )

                    remove_subsequent(deferred_fragment_record)
            return
        deferred_grouped_field_set_result = cast(
            "ReconcilableDeferredGroupedFieldSetResult",
            deferred_grouped_field_set_result,
        )
        for deferred_fragment_record in (
            deferred_grouped_field_set_result.deferred_fragment_records
        ):  # pragma: no branch
            deferred_fragment_record.reconcilable_results.append(
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
        for deferred_fragment_record in (
            deferred_grouped_field_set_result.deferred_fragment_records
        ):  # pragma: no branch
            id_ = deferred_fragment_record.id
            if id_ is None:
                continue  # pragma: no cover
            reconcilable_results = complete_deferred(deferred_fragment_record)
            if reconcilable_results is None:
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
            append_completed(CompletedResult(id_))

    async def _handle_completed_stream_items(
        self, stream_items_result: StreamItemsResult
    ) -> None:
        """Handle completed stream."""
        stream_record = stream_items_result.stream_record
        id_ = stream_record.id
        if id_ is None:
            return  # pragma: no cover
        incremental_graph = self._incremental_graph
        if stream_items_result.errors is not None:
            self._completed.append(CompletedResult(id_, stream_items_result.errors))
            incremental_graph.remove_subsequent_result_record(stream_record)
            if is_cancellable_stream_record(stream_record):
                cancellable_streams = self._context.cancellable_streams
                if cancellable_streams:  # pragma: no branch
                    cancellable_streams.discard(stream_record)
                with suppress(Exception):
                    await stream_record.early_return
        elif stream_items_result.result is None:
            self._completed.append(CompletedResult(id_))
            incremental_graph.remove_subsequent_result_record(stream_record)
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
                incremental_graph.add_incremental_data_records(
                    stream_items_result.incremental_data_records
                )

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
        for deferred_fragment_record in (
            deferred_grouped_field_set_result.deferred_fragment_records
        ):  # pragma: no branch
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
