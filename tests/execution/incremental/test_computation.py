from __future__ import annotations

from asyncio import CancelledError, Event, Future, sleep
from typing import TYPE_CHECKING, Any

import pytest

from graphql.execution.incremental import Computation

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class Spy:
    """Wrap a function, counting its calls."""

    def __init__(self, fn: Callable[..., Any]) -> None:
        self.fn = fn
        self.call_count = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.call_count += 1
        return self.fn(*args, **kwargs)


def describe_computation():
    def can_return_a_result():
        computation = Computation(lambda: {"value": 123})

        assert computation.result() == {"value": 123}

    def can_be_started_manually():
        computation = Computation(lambda: {"value": 123})

        computation.prime()
        assert computation.result() == {"value": 123}

    def only_runs_once_when_started_multiple_times():
        run_spy = Spy(lambda: {"value": "done"})
        computation = Computation(run_spy)

        computation.prime()
        computation.prime()
        computation.prime()
        results = [computation.result() for _ in range(3)]

        assert results == [{"value": "done"}] * 3
        assert run_spy.call_count == 1

    async def stores_async_result_via_result():
        async def run() -> dict[str, str]:
            await sleep(0)
            return {"value": "done"}

        run_spy = Spy(run)
        computation = Computation(run_spy)

        computation.prime()
        computation.prime()
        computation.prime()
        assert await computation.result() == {"value": "done"}
        results = [computation.result() for _ in range(3)]

        assert results == [{"value": "done"}] * 3
        assert run_spy.call_count == 1

    def stores_sync_error_in_result():
        def run() -> None:
            raise RuntimeError("failure")

        run_spy = Spy(run)
        computation = Computation(run_spy)

        computation.prime()  # does not raise
        with pytest.raises(RuntimeError, match="failure"):
            computation.result()
        with pytest.raises(RuntimeError, match="failure"):
            computation.result()
        assert run_spy.call_count == 1

    async def stores_async_error_in_result():
        async def run() -> None:
            await sleep(0)
            raise RuntimeError("failure")

        run_spy = Spy(run)
        computation = Computation(run_spy)

        computation.prime()  # does not raise
        with pytest.raises(RuntimeError, match="failure"):
            await computation.result()
        with pytest.raises(RuntimeError, match="failure"):
            computation.result()
        assert run_spy.call_count == 1

    def can_be_aborted_before_running():
        on_abort_spy = Spy(lambda _reason: None)
        run_spy = Spy(lambda: {"value": 123})
        computation = Computation(run_spy, on_abort_spy)

        computation.abort(RuntimeError("Cancelled!"))
        with pytest.raises(RuntimeError, match="Cancelled!"):
            computation.result()
        assert on_abort_spy.call_count == 0
        assert run_spy.call_count == 0

    def cannot_be_aborted_after_running_synchronously():
        on_abort_spy = Spy(lambda _reason: None)
        computation = Computation(lambda: {"value": 123}, on_abort_spy)

        computation.prime()
        computation.abort()
        assert computation.result() == {"value": 123}
        assert on_abort_spy.call_count == 0

    def cannot_be_aborted_after_erroring_synchronously():
        def run() -> None:
            raise RuntimeError("failure")

        on_abort_spy = Spy(lambda _reason: None)
        computation: Computation[Any] = Computation(run, on_abort_spy)

        computation.prime()
        computation.abort()
        with pytest.raises(RuntimeError, match="failure"):
            computation.result()
        assert on_abort_spy.call_count == 0

    async def can_be_aborted_while_running_asynchronously():
        async def run() -> None:
            # may be cancelled before it even starts running
            await Event().wait()  # pragma: no cover

        on_abort_spy = Spy(lambda _reason: None)
        computation: Computation[Any] = Computation(run, on_abort_spy)

        computation.prime()
        computation.abort(RuntimeError("Cancelled!"))
        assert on_abort_spy.call_count == 1
        with pytest.raises(RuntimeError, match="Cancelled!"):
            computation.result()
        await sleep(0)  # let the cancelled future settle

    async def returns_async_abort_cleanup_while_running():
        async def run() -> None:
            # may be cancelled before it even starts running
            await Event().wait()  # pragma: no cover

        cleanup_future: Future[None] = Future()
        computation: Computation[Any] = Computation(run, lambda _reason: cleanup_future)

        computation.prime()
        abort_result = computation.abort()
        assert abort_result is cleanup_future
        assert not cleanup_future.done()
        cleanup_future.set_result(None)
        await cleanup_future
        await sleep(0)  # let the cancelled future settle

    def can_be_aborted_with_a_provided_reason_before_running():
        abort_reason = RuntimeError("aborted")
        computation = Computation(lambda: {"value": 123})

        computation.abort(abort_reason)
        with pytest.raises(RuntimeError, match="aborted") as exc_info:
            computation.result()
        assert exc_info.value is abort_reason

    async def forwards_abort_reason_to_on_abort_while_running_asynchronously():
        async def run() -> None:
            # may be cancelled before it even starts running
            await Event().wait()  # pragma: no cover

        abort_reason = RuntimeError("aborted")
        recorded_reasons: list[BaseException | None] = []
        computation: Computation[Any] = Computation(run, recorded_reasons.append)

        computation.prime()
        computation.abort(abort_reason)
        assert recorded_reasons == [abort_reason]
        with pytest.raises(RuntimeError, match="aborted"):
            computation.result()
        await sleep(0)  # let the cancelled future settle

    def aborting_without_reason_raises_a_cancelled_error():
        computation = Computation(lambda: {"value": 123})

        computation.abort()
        with pytest.raises(CancelledError):
            computation.result()

    def repeated_aborts_are_ignored():
        computation = Computation(lambda: {"value": 123})

        computation.abort(RuntimeError("first"))
        computation.abort(RuntimeError("second"))
        with pytest.raises(RuntimeError, match="first"):
            computation.result()

    async def can_be_aborted_while_running_without_abort_callback():
        async def run() -> None:
            # may be cancelled before it even starts running
            await Event().wait()  # pragma: no cover

        computation: Computation[Any] = Computation(run)

        computation.prime()
        assert computation.abort(RuntimeError("Cancelled!")) is None
        with pytest.raises(RuntimeError, match="Cancelled!"):
            computation.result()
        await sleep(0)  # let the cancelled future settle

    async def cannot_be_aborted_after_completing_asynchronously():
        async def run() -> dict[str, int]:
            return {"value": 123}

        on_abort_spy = Spy(lambda _reason: None)
        computation: Computation[Any] = Computation(run, on_abort_spy)

        computation.prime()
        assert await computation.result() == {"value": 123}
        computation.abort()
        assert computation.result() == {"value": 123}
        assert on_abort_spy.call_count == 0

    async def rejects_when_the_pending_future_is_cancelled_externally():
        async def run() -> None:
            # may be cancelled before it even starts running
            await Event().wait()  # pragma: no cover

        computation: Computation[Any] = Computation(run)

        future = computation.result()
        assert isinstance(future, Future)
        future.cancel()
        with pytest.raises(CancelledError):
            await future
        with pytest.raises(CancelledError):
            computation.result()

    async def abort_wins_when_racing_async_completion():
        async def run() -> dict[str, int]:
            return {"value": 123}

        computation: Computation[Any] = Computation(run)

        computation.prime()
        await sleep(0)  # future completes, but memoization is still queued
        computation.abort(RuntimeError("Cancelled!"))
        await sleep(0)  # run the queued memoization callback
        with pytest.raises(RuntimeError, match="Cancelled!"):
            computation.result()
