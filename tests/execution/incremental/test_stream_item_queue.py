"""Unit tests for the stream item queue.

These tests cover the asyncio-specific seams of the stream item queue that
are not (or not deterministically) reachable via the defer/stream test
suites, especially the batching of pending entries and the abort paths.
"""

from __future__ import annotations

from asyncio import (
    CancelledError,
    Event,
    Future,
    ensure_future,
    get_running_loop,
    sleep,
)
from typing import TYPE_CHECKING, Any

import pytest

from graphql.execution.incremental import StreamItemQueue, WorkResult
from graphql.pyutils import is_awaitable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_queue(
    produce: Callable[[StreamItemQueue], Any],
    on_abort: Callable[[BaseException | None], Awaitable[None] | None] | None = None,
    eager: bool = False,
    capacity: int = 100,
) -> StreamItemQueue:
    return StreamItemQueue(produce, on_abort, eager=eager, capacity=capacity)


async def collect_batches(queue: StreamItemQueue) -> list[Sequence[WorkResult]]:
    return [batch async for batch in queue.batches()]


def describe_stream_item_queue():
    async def delivers_settled_results_in_one_batch():
        async def produce(queue: StreamItemQueue) -> None:
            await queue.push(WorkResult(1))
            await queue.push(WorkResult(2))

        queue = make_queue(produce)
        assert not queue.is_stopped()
        batches = await collect_batches(queue)
        assert batches == [[WorkResult(1), WorkResult(2)]]
        assert queue.is_stopped()

    async def delivers_batches_in_order_with_pending_futures():
        loop_futures: list[Future[WorkResult]] = []

        async def produce(queue: StreamItemQueue) -> None:
            loop = get_running_loop()
            first: Future[WorkResult] = loop.create_future()
            second: Future[WorkResult] = loop.create_future()
            loop_futures.extend([first, second])
            await queue.push(first)
            await queue.push(second)
            await queue.push(WorkResult(3))
            # settle out of order: the batches must stay in source order
            second.set_result(WorkResult(2))
            first.set_result(WorkResult(1))

        queue = make_queue(produce)
        batches = await collect_batches(queue)
        assert batches in (
            [[WorkResult(1), WorkResult(2), WorkResult(3)]],
            [[WorkResult(1)], [WorkResult(2), WorkResult(3)]],
        )

    async def holds_back_pending_futures_at_the_end_of_a_batch():
        release = Event()

        async def produce(queue: StreamItemQueue) -> None:
            await queue.push(WorkResult(1))
            loop = get_running_loop()
            future: Future[WorkResult] = loop.create_future()
            await queue.push(future)

            async def settle_later() -> None:
                await release.wait()
                future.set_result(WorkResult(2))

            task = ensure_future(settle_later())
            release.set()
            await task

        queue = make_queue(produce)
        batches = await collect_batches(queue)
        assert batches == [[WorkResult(1)], [WorkResult(2)]]

    async def raises_stream_failure_after_delivering_settled_results():
        error = RuntimeError("stream failed")

        async def produce(queue: StreamItemQueue) -> None:
            await queue.push(WorkResult(1))
            raise error

        queue = make_queue(produce)
        batches: list[Sequence[WorkResult]] = []

        async def consume() -> None:
            async for batch in queue.batches():
                batches.append(batch)  # noqa: PERF401

        with pytest.raises(RuntimeError, match="stream failed"):
            await consume()
        assert batches == [[WorkResult(1)]]
        assert not queue.is_stopped()

    async def runs_cleanup_before_delivering_a_stream_failure():
        cleaned_up: list[BaseException | None] = []

        async def produce(_queue: StreamItemQueue) -> None:
            raise RuntimeError("stream failed")

        async def async_cleanup() -> None:
            cleaned_up.append(None)

        def on_abort(reason: BaseException | None) -> Awaitable[None]:
            cleaned_up.append(reason)
            return async_cleanup()

        queue = make_queue(produce, on_abort)
        with pytest.raises(RuntimeError, match="stream failed"):
            await collect_batches(queue)
        assert len(cleaned_up) == 2
        assert isinstance(cleaned_up[0], RuntimeError)

    async def delivers_rejection_of_a_pending_head_after_cleanup():
        aborted: list[BaseException | None] = []

        async def produce(queue: StreamItemQueue) -> None:
            loop = get_running_loop()
            failing: Future[WorkResult] = loop.create_future()
            failing.set_exception(RuntimeError("item failed"))
            await queue.push(failing)
            await Event().wait()  # never finishes normally

        queue = make_queue(produce, aborted.append)
        with pytest.raises(RuntimeError, match="item failed"):
            await collect_batches(queue)
        assert len(aborted) == 1
        assert queue.abort() is None  # already aborted

    async def holds_back_a_rejected_future_at_the_end_of_a_batch():
        async def produce(queue: StreamItemQueue) -> None:
            await queue.push(WorkResult(1))
            loop = get_running_loop()
            failing: Future[WorkResult] = loop.create_future()
            failing.set_exception(RuntimeError("item failed"))
            await queue.push(failing)

        queue = make_queue(produce)
        batches: list[Sequence[WorkResult]] = []

        async def consume() -> None:
            async for batch in queue.batches():
                batches.append(batch)  # noqa: PERF401

        with pytest.raises(RuntimeError, match="item failed"):
            await consume()
        assert batches == [[WorkResult(1)]]

    async def starts_the_producer_eagerly_when_a_loop_is_running():
        started = Event()

        async def produce(queue: StreamItemQueue) -> None:
            started.set()
            await queue.push(WorkResult(1))

        queue = make_queue(produce, eager=True)
        await sleep(0)
        assert started.is_set()  # started before consumption
        batches = await collect_batches(queue)
        assert batches == [[WorkResult(1)]]

    def starts_the_producer_lazily_without_a_running_loop():
        async def produce(_queue: StreamItemQueue) -> None:
            return  # pragma: no cover

        queue = make_queue(produce, eager=True)  # no loop running here
        assert queue._producer_task is None  # noqa: SLF001

    async def aborting_an_unconsumed_queue_runs_the_cleanup_synchronously():
        aborted: list[BaseException | None] = []

        async def produce(_queue: StreamItemQueue) -> None:
            return  # pragma: no cover

        queue = make_queue(produce, aborted.append)
        reason = RuntimeError("abort")
        assert queue.abort(reason) is None
        assert aborted == [reason]

    async def aborting_a_started_queue_cancels_the_producer():
        aborted: list[BaseException | None] = []
        parked = Event()

        async def produce(_queue: StreamItemQueue) -> None:
            parked.set()
            await Event().wait()  # park forever

        queue = make_queue(produce, aborted.append, eager=True)
        await parked.wait()
        cleanup = queue.abort()
        assert is_awaitable(cleanup)
        await cleanup
        assert aborted == [None]
        producer_task = queue._producer_task  # noqa: SLF001
        assert producer_task is not None
        assert producer_task.cancelled()

    async def aborting_a_started_queue_cancels_pending_item_futures():
        pending: list[Future[WorkResult]] = []

        async def parked_item() -> WorkResult:
            await Event().wait()  # park forever
            return WorkResult(None)  # pragma: no cover

        async def produce(queue: StreamItemQueue) -> None:
            future = ensure_future(parked_item())
            pending.append(future)
            await queue.push(future)

        queue = make_queue(produce, eager=True)
        while not pending:  # noqa: ASYNC110
            await sleep(0)
        await sleep(0)  # let the producer finish normally
        cleanup = queue.abort()
        assert is_awaitable(cleanup)
        await cleanup
        assert pending[0].cancelled()

    async def aborting_an_unconsumed_queue_without_cleanup_callback():
        async def produce(_queue: StreamItemQueue) -> None:
            return  # pragma: no cover

        queue = make_queue(produce)
        assert queue.abort() is None

    async def awaiting_cleanup_settles_pending_item_futures():
        pushed = Event()

        async def parked_item() -> WorkResult:
            await Event().wait()  # park forever
            return WorkResult(None)  # pragma: no cover

        async def produce(queue: StreamItemQueue) -> None:
            await queue.push(ensure_future(parked_item()))
            pushed.set()
            await Event().wait()  # park forever

        queue = make_queue(produce, eager=True)
        await pushed.wait()
        cleanup = queue.abort()
        assert is_awaitable(cleanup)
        await cleanup

    async def aborting_after_normal_finish_skips_the_cleanup_callback():
        aborted: list[BaseException | None] = []

        async def produce(queue: StreamItemQueue) -> None:
            await queue.push(WorkResult(1))

        queue = make_queue(produce, aborted.append)
        batches = await collect_batches(queue)
        assert batches == [[WorkResult(1)]]
        assert queue.abort() is None
        assert aborted == []  # the source finished and must not be cleaned up

    async def awaiting_cleanup_awaits_the_abort_callback():
        cleanup_done = Event()
        parked = Event()

        async def produce(_queue: StreamItemQueue) -> None:
            parked.set()
            await Event().wait()  # park forever

        async def async_cleanup() -> None:
            await sleep(0)
            cleanup_done.set()

        def on_abort(_reason: BaseException | None) -> Awaitable[None]:
            return async_cleanup()

        queue = make_queue(produce, on_abort, eager=True)
        await parked.wait()
        cleanup = queue.abort()
        assert is_awaitable(cleanup)
        await cleanup
        assert cleanup_done.is_set()

    async def consumer_cancellation_does_not_settle_pending_items():
        pushed = Event()

        async def produce(queue: StreamItemQueue) -> None:
            future: Future[WorkResult] = get_running_loop().create_future()
            await queue.push(future)
            pushed.set()
            await Event().wait()  # park forever

        queue = make_queue(produce)

        async def consume() -> None:
            async for _batch in queue.batches():  # pragma: no cover
                pass

        consumer = ensure_future(consume())
        await pushed.wait()
        consumer.cancel()
        with pytest.raises(CancelledError):
            await consumer
        cleanup = queue.abort()
        assert is_awaitable(cleanup)
        await cleanup
