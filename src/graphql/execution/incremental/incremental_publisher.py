"""Incremental publisher"""

from __future__ import annotations

from asyncio import FIRST_COMPLETED, ensure_future, wait
from typing import TYPE_CHECKING, Any, Protocol, cast

from ...error import GraphQLError, located_error
from ..types import (
    CompletedResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalDeferResult,
    IncrementalStreamResult,
    InitialIncrementalExecutionResult,
    PendingResult,
    SubsequentIncrementalExecutionResult,
)
from .work_queue import (
    GroupFailureEvent,
    GroupSuccessEvent,
    GroupValuesEvent,
    StreamFailureEvent,
    StreamSuccessEvent,
    StreamValuesEvent,
    WorkQueue,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from ...pyutils import AbortSignal
    from ..types import IncrementalResult
    from .incremental_executor import (
        DeliveryGroup,
        ExecutionGroupValue,
        ItemStream,
        StreamItemValue,
    )
    from .work_queue import Work, WorkQueueEvent

__all__ = [
    "IncrementalPublisher",
    "IncrementalPublisherContext",
]


class IncrementalPublisherContext(Protocol):
    """The context for incremental publishing."""

    abort_signal: AbortSignal | None

    def abort_error(self) -> Exception:
        """Return the exception to raise when execution has been aborted."""
        ...  # pragma: no cover

    async def cancel_incremental_work(
        self, reason: BaseException | None = None
    ) -> None:
        """Cancel all pending incremental work and close the stream sources."""
        ...  # pragma: no cover

    def run_async_work_finished_hook(self) -> None:
        """Run the hook signaling that all asynchronous work has finished."""
        ...  # pragma: no cover


class _SubsequentResultContext:
    """The context collecting the parts of a subsequent incremental result."""

    __slots__ = "completed", "has_next", "incremental", "pending"

    def __init__(self) -> None:
        self.pending: list[PendingResult] = []
        self.incremental: list[IncrementalResult] = []
        self.completed: list[CompletedResult] = []
        self.has_next = True


class IncrementalPublisher:
    """Publish incremental results.

    This class is used to publish incremental results to the client, enabling
    semi-concurrent execution while preserving result order. It translates the
    work queue events into incremental execution results, assigning the ids of
    the pending results.

    For internal use only.
    """

    _ids: dict[DeliveryGroup | ItemStream, str]
    _next_id: int

    def __init__(self) -> None:
        self._ids = {}
        self._next_id = 0

    def build_response(
        self,
        data: dict[str, Any],
        errors: list[GraphQLError] | None,
        work: Work,
        context: IncrementalPublisherContext,
    ) -> ExperimentalIncrementalExecutionResults:
        """Build the initial response and the subsequent result stream."""
        work_queue = WorkQueue(work)

        pending = self._to_pending_results(
            cast("Sequence[DeliveryGroup]", work_queue.initial_groups),
            cast("Sequence[ItemStream]", work_queue.initial_streams),
        )

        initial_result = InitialIncrementalExecutionResult(
            data,
            errors,
            pending=pending,
            has_next=True,
        )

        return ExperimentalIncrementalExecutionResults(
            initial_result, self._subscribe(work_queue, context)
        )

    def _ensure_id(self, node: DeliveryGroup | ItemStream) -> str:
        """Get the id assigned to the given node, assigning one if needed."""
        id_ = self._ids.get(node)
        if id_ is None:
            id_ = str(self._next_id)
            self._next_id += 1
            self._ids[node] = id_
        return id_

    def _to_pending_results(
        self,
        new_groups: Sequence[DeliveryGroup],
        new_streams: Sequence[ItemStream],
    ) -> list[PendingResult]:
        """Convert new delivery groups and streams to pending results."""
        pending_results: list[PendingResult] = []
        nodes: list[DeliveryGroup | ItemStream] = [*new_groups, *new_streams]
        for node in nodes:
            id_ = self._ensure_id(node)
            path = node.path
            pending_results.append(
                PendingResult(id_, path.as_list() if path else [], node.label)
            )
        return pending_results

    async def _subscribe(
        self,
        work_queue: WorkQueue,
        context: IncrementalPublisherContext,
    ) -> AsyncGenerator[SubsequentIncrementalExecutionResult, None]:
        """Subscribe to the incremental results."""
        abort_signal = context.abort_signal
        events = work_queue.events()
        try:
            while True:
                if abort_signal is not None and abort_signal.aborted:
                    raise context.abort_error()

                next_batch = ensure_future(anext(events))
                if abort_signal is None:
                    try:
                        batch = await next_batch
                    except StopAsyncIteration:
                        return
                else:
                    # reject the pending request when the operation is aborted
                    abort = ensure_future(abort_signal.wait())
                    try:
                        await wait({next_batch, abort}, return_when=FIRST_COMPLETED)
                    finally:
                        if not abort.done():
                            abort.cancel()
                    if abort_signal.aborted:
                        next_batch.cancel()
                        raise context.abort_error()
                    try:
                        batch = next_batch.result()
                    except StopAsyncIteration:
                        return

                subsequent_result = self._handle_batch(batch)
                yield subsequent_result

                if not subsequent_result.has_next:
                    return
        finally:
            await work_queue.cancel()
            await context.cancel_incremental_work()
            context.run_async_work_finished_hook()

    def _handle_batch(
        self, batch: Sequence[WorkQueueEvent]
    ) -> SubsequentIncrementalExecutionResult:
        """Translate a batch of work queue events into a subsequent result."""
        context = _SubsequentResultContext()

        for event in batch:
            self._handle_work_queue_event(event, context)

        return SubsequentIncrementalExecutionResult(
            has_next=context.has_next,
            pending=context.pending or None,
            incremental=context.incremental or None,
            completed=context.completed or None,
        )

    def _handle_work_queue_event(
        self,
        event: WorkQueueEvent,
        context: _SubsequentResultContext,
    ) -> None:
        """Translate a single work queue event."""
        if isinstance(event, GroupValuesEvent):
            group = cast("DeliveryGroup", event.group)
            id_ = self._ensure_id(group)
            for value in cast("Sequence[ExecutionGroupValue]", event.values):
                best_id, sub_path = self._get_best_id_and_sub_path(id_, group, value)
                context.incremental.append(
                    IncrementalDeferResult(
                        data=value.data,
                        id=best_id,
                        sub_path=sub_path,
                        errors=value.errors,
                    )
                )
        elif isinstance(event, GroupSuccessEvent):
            group = cast("DeliveryGroup", event.group)
            context.completed.append(CompletedResult(self._ensure_id(group)))
            del self._ids[group]
            if event.new_groups or event.new_streams:
                context.pending.extend(
                    self._to_pending_results(
                        cast("Sequence[DeliveryGroup]", event.new_groups),
                        cast("Sequence[ItemStream]", event.new_streams),
                    )
                )
        elif isinstance(event, GroupFailureEvent):
            group = cast("DeliveryGroup", event.group)
            context.completed.append(
                CompletedResult(
                    self._ensure_id(group), [ensure_graphql_error(event.error)]
                )
            )
            del self._ids[group]
        elif isinstance(event, StreamValuesEvent):
            stream = cast("ItemStream", event.stream)
            id_ = self._ensure_id(stream)
            items: list[Any] = []
            errors: list[GraphQLError] = []
            for item_value in cast("Sequence[StreamItemValue]", event.values):
                items.append(item_value.item)
                if item_value.errors:
                    errors.extend(item_value.errors)
            context.incremental.append(
                IncrementalStreamResult(items=items, id=id_, errors=errors or None)
            )
            if event.new_groups or event.new_streams:
                context.pending.extend(
                    self._to_pending_results(
                        cast("Sequence[DeliveryGroup]", event.new_groups),
                        cast("Sequence[ItemStream]", event.new_streams),
                    )
                )
        elif isinstance(event, StreamSuccessEvent):
            stream = cast("ItemStream", event.stream)
            context.completed.append(CompletedResult(self._ensure_id(stream)))
            del self._ids[stream]
        elif isinstance(event, StreamFailureEvent):
            stream = cast("ItemStream", event.stream)
            context.completed.append(
                CompletedResult(
                    self._ensure_id(stream), [ensure_graphql_error(event.error)]
                )
            )
            del self._ids[stream]
        else:  # WorkQueueTerminationEvent
            context.has_next = False

    def _get_best_id_and_sub_path(
        self,
        initial_id: str,
        initial_delivery_group: DeliveryGroup,
        value: ExecutionGroupValue,
    ) -> tuple[str, list[str | int] | None]:
        """Get the best id and sub path for an execution group value."""
        path = initial_delivery_group.path
        max_length = len(path.as_list()) if path else 0
        best_id = initial_id

        for delivery_group in value.delivery_groups:
            if delivery_group is initial_delivery_group:
                continue
            id_ = self._ids.get(delivery_group)
            if id_ is None:
                continue
            group_path = delivery_group.path
            length = len(group_path.as_list()) if group_path else 0
            if length > max_length:
                max_length = length
                best_id = id_

        sub_path = value.path[max_length:]
        return best_id, sub_path or None


def ensure_graphql_error(error: BaseException) -> GraphQLError:
    """Ensure that the given error is returned as a GraphQL error."""
    if isinstance(error, GraphQLError):
        return error
    if isinstance(error, Exception):
        return located_error(error)
    # BaseExceptions like CancelledError normally do not surface here,
    # since cancellation stops the delivery of events.
    return GraphQLError(str(error) or repr(error))
