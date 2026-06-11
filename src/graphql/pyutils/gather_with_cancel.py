"""Run awaitables concurrently with cancellation support."""

from __future__ import annotations

from asyncio import Future, ensure_future, gather
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable

__all__ = ["gather_with_cancel"]


async def gather_with_cancel(*awaitables: Awaitable[Any]) -> list[Any]:
    """Run awaitable objects in the sequence concurrently.

    The first raised exception is immediately propagated to the task that awaits
    on this function and all pending awaitables in the sequence will be cancelled.

    This is different from the default behavior or `asyncio.gather` which waits
    for all tasks to complete even if one of them raises an exception. It is also
    different from `asyncio.gather` with `return_exceptions` set, which does not
    cancel the other tasks when one of them raises an exception.
    """
    futures: list[Future[Any]] = [ensure_future(aw) for aw in awaitables]
    try:
        return await gather(*futures)
    except Exception:
        for future in futures:
            if not future.done():
                future.cancel()
        await gather(*futures, return_exceptions=True)
        raise
