"""Run awaitables concurrently with cancellation support."""

from __future__ import annotations

from asyncio import Task, create_task, gather
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
    try:
        tasks: list[Task[Any]] = [
            aw if isinstance(aw, Task) else create_task(aw)  # type: ignore[arg-type]
            for aw in awaitables
        ]
    except TypeError:
        return await gather(*awaitables)
    try:
        return await gather(*tasks)
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await gather(*tasks, return_exceptions=True)
        raise
