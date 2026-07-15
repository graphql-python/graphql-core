"""Unit tests for the incremental publisher.

These tests cover defensive seams of the incremental publisher that are not
reachable via the defer/stream test suites.
"""

from __future__ import annotations

from asyncio import CancelledError
from typing import TYPE_CHECKING

import pytest

from graphql.error import GraphQLError
from graphql.execution.incremental import IncrementalPublisher
from graphql.execution.incremental.incremental_publisher import ensure_graphql_error
from graphql.pyutils import AbortController

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from graphql.execution.incremental import WorkQueueEvent

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeWorkQueue:
    """A fake work queue whose events end without a termination event."""

    def __init__(self) -> None:
        self.cancelled = False

    async def events(self) -> AsyncIterator[Sequence[WorkQueueEvent]]:
        return
        yield []  # pragma: no cover

    async def cancel(self, _reason: BaseException | None = None) -> None:
        self.cancelled = True


class FakeContext:
    """A fake incremental publisher context."""

    def __init__(self) -> None:
        self.abort_signal = None
        self.cancelled = False
        self.hook_run = False

    def abort_error(self) -> Exception:
        return RuntimeError("aborted")  # pragma: no cover

    async def cancel_incremental_work(
        self, _reason: BaseException | None = None
    ) -> None:
        self.cancelled = True

    def run_async_work_finished_hook(self) -> None:
        self.hook_run = True


def describe_incremental_publisher():
    async def stops_when_the_work_queue_ends_without_termination():
        work_queue = FakeWorkQueue()
        context = FakeContext()
        publisher = IncrementalPublisher()
        results = [
            result
            async for result in publisher._subscribe(  # noqa: SLF001
                work_queue,  # type: ignore[arg-type]
                context,  # type: ignore[arg-type]
            )
        ]
        assert results == []
        assert work_queue.cancelled
        assert context.cancelled
        assert context.hook_run

    async def stops_when_work_queue_ends_without_termination_with_abort_signal():
        work_queue = FakeWorkQueue()
        context = FakeContext()
        context.abort_signal = AbortController().signal  # type: ignore[assignment]
        publisher = IncrementalPublisher()
        results = [
            result
            async for result in publisher._subscribe(  # noqa: SLF001
                work_queue,  # type: ignore[arg-type]
                context,  # type: ignore[arg-type]
            )
        ]
        assert results == []
        assert work_queue.cancelled
        assert context.cancelled
        assert context.hook_run

    def describe_ensure_graphql_error():
        def passes_graphql_errors_through():
            error = GraphQLError("test")
            assert ensure_graphql_error(error) is error

        def locates_plain_exceptions():
            error = RuntimeError("test")
            graphql_error = ensure_graphql_error(error)
            assert isinstance(graphql_error, GraphQLError)
            assert graphql_error.message == "test"
            assert graphql_error.original_error is error

        def converts_base_exceptions():
            error: BaseException = CancelledError()
            graphql_error = ensure_graphql_error(error)
            assert isinstance(graphql_error, GraphQLError)
            assert graphql_error.message == "CancelledError()"
