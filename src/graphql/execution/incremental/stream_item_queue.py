"""Queue of stream item results"""

from __future__ import annotations

from asyncio import (
    Event,
    Future,
    Queue,
    QueueEmpty,
    ensure_future,
    gather,
    get_running_loop,
    isfuture,
)
from typing import TYPE_CHECKING, Any, NamedTuple

from ...pyutils.is_awaitable import is_awaitable

if TYPE_CHECKING:
    from asyncio import Task
    from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Sequence

    from .work_queue import WorkResult

__all__ = ["StreamItemQueue"]

_END: Any = object()  # sentinel marking the normal end of the stream


class _ErrorEntry(NamedTuple):
    """An entry marking the failure of the stream."""

    error: BaseException


class StreamItemQueue:
    """An ordered queue of stream item results with back-pressure.

    The queue is fed by a producer coroutine which pushes the stream item
    results in source order, either settled or as pending futures when items
    are completed early. The queue buffers up to ``capacity`` entries; when
    the buffer is full, pushing blocks, which paces the producer.

    The batches of settled results are consumed via :meth:`batches`, which
    preserves the source order: a still pending head entry delays delivery,
    while consecutive already settled entries are delivered together in one
    batch. This implements the stream queue interface consumed by the
    :class:`~graphql.execution.incremental.WorkQueue` scheduler.

    In eager mode, the producer is started as soon as possible; otherwise it
    is started lazily when the batches are first consumed.

    Aborting the queue cancels the producer and all pending item futures and
    awaits their cancellation before running the cleanup callback, so that no
    asynchronous work is left behind unsettled.

    For internal use only.
    """

    def __init__(
        self,
        produce: Callable[[StreamItemQueue], Coroutine[Any, Any, None]],
        on_abort: Callable[[BaseException | None], Awaitable[None] | None]
        | None = None,
        eager: bool = False,
        capacity: int = 100,
    ) -> None:
        """Initialize the queue with a producer and an abort callback."""
        self._produce = produce
        self._on_abort = on_abort
        self._eager = eager
        self._entries: Queue[Any] = Queue(capacity)
        self._started = Event()
        self._producer_task: Task[None] | None = None
        self._pending_futures: set[Future[WorkResult]] = set()
        self._aborted = False
        self._finished = False
        self._stopped = False
        if eager:
            try:
                get_running_loop()
            except RuntimeError:
                pass  # no running event loop yet, start on first consumption
            else:
                self._start()

    def _start(self) -> None:
        """Start the producer task if it has not been started yet."""
        if self._producer_task is None and not self._aborted:
            self._producer_task = ensure_future(self._run())

    async def _run(self) -> None:
        """Run the producer, finishing the queue when it is done."""
        if not self._eager:
            await self._started.wait()
        entries = self._entries
        try:
            await self._produce(self)
        except Exception as error:
            # settle the pending item futures and clean up the source
            # before delivering the failure
            self._aborted = True
            await self._settle_pending()
            on_abort = self._on_abort
            if on_abort is not None:
                cleanup = on_abort(error)
                if is_awaitable(cleanup):
                    await cleanup
            await entries.put(_ErrorEntry(error))
        else:
            self._finished = True
            await entries.put(_END)

    async def push(self, result: WorkResult | Future[WorkResult]) -> None:
        """Push a settled or still pending stream item result onto the queue.

        Blocks when the queue has reached its capacity, pacing the producer.
        """
        if isfuture(result):
            pending_futures = self._pending_futures
            pending_futures.add(result)
            result.add_done_callback(pending_futures.discard)
        await self._entries.put(result)

    async def batches(self) -> AsyncIterator[Sequence[WorkResult]]:
        """Iterate over the batches of settled stream item results in order.

        Starts the producer on the first iteration step. A failure of the
        stream is raised only after all results settled before the failure
        have been delivered.
        """
        self._start()
        self._started.set()
        entries = self._entries
        held: Any = None
        while True:
            entry = await entries.get() if held is None else held
            held = None
            if isfuture(entry):
                try:
                    entry = await entry
                except Exception:
                    await self._cleanup()
                    raise
            if entry is _END:
                self._stopped = True
                return
            if isinstance(entry, _ErrorEntry):
                raise entry.error
            batch = [entry]
            while True:
                try:
                    next_entry = entries.get_nowait()
                except QueueEmpty:
                    break
                if next_entry is _END:
                    # allow peeking ahead to see that the stream has stopped
                    self._stopped = True
                    held = next_entry  # finish after delivering this batch
                    break
                if isinstance(next_entry, _ErrorEntry) or (
                    isfuture(next_entry) and not next_entry.done()
                ):
                    held = next_entry  # deliver the current batch first
                    break
                if isfuture(next_entry):
                    try:
                        next_entry = next_entry.result()
                    except Exception:
                        held = next_entry  # re-raise when delivered as head
                        break
                batch.append(next_entry)
            yield batch

    def is_stopped(self) -> bool:
        """Check whether the stream is known to have stopped normally."""
        return self._stopped

    def abort(self, reason: BaseException | None = None) -> Awaitable[None] | None:
        """Abort the stream with an optional reason.

        Cancels the producer and the pending item futures and returns an
        awaitable for the asynchronous part of the cleanup, or None when the
        whole cleanup could be run synchronously.
        """
        if self._aborted:
            return None
        self._aborted = True
        if self._finished:
            # The source finished normally, so it must not be cleaned up;
            # only settle any still pending early executed item futures.
            if not self._pending_futures:
                return None
            for future in self._pending_futures:
                future.cancel()
            return self._settle_pending()
        producer_task = self._producer_task
        if producer_task is not None and not producer_task.done():
            producer_task.cancel()
        for future in self._pending_futures:
            future.cancel()
        if (producer_task is None or producer_task.done()) and (
            not self._pending_futures
        ):
            # nothing to cancel asynchronously, just run the cleanup callback
            on_abort = self._on_abort
            if on_abort is not None:
                cleanup = on_abort(reason)
                if is_awaitable(cleanup):
                    return cleanup
            return None
        return self._cleanup(reason)

    async def _settle_pending(self) -> None:
        """Cancel and settle all still pending item futures."""
        pending = [future for future in self._pending_futures if not future.done()]
        if pending:
            for future in pending:
                future.cancel()
            await gather(*pending, return_exceptions=True)

    async def _cleanup(self, reason: BaseException | None = None) -> None:
        """Cancel all pending work, awaiting it, and run the abort callback."""
        self._aborted = True
        producer_task = self._producer_task
        if producer_task is not None and not producer_task.done():
            producer_task.cancel()
            await gather(producer_task, return_exceptions=True)
        await self._settle_pending()
        on_abort = self._on_abort
        if on_abort is not None:
            cleanup = on_abort(reason)
            if is_awaitable(cleanup):
                await cleanup
