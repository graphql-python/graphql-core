from __future__ import annotations  # Python < 3.10

from typing import Any, AsyncIterable, Awaitable, Callable


__all__ = ["map_async_iterable"]


async def map_async_iterable(
    iterable: AsyncIterable[Any], callback: Callable[[Any], Awaitable[Any]]
) -> None:
    """Map an AsyncIterable over a callback function.

    Given an AsyncIterable and an async callback callable, return an AsyncGenerator
    which produces values mapped via calling the callback.
    If the inner iterator supports an `aclose()` method, it will be called when
    the generator finishes or closes.
    """

    aiter = iterable.__aiter__()
    try:
        async for element in aiter:
            yield await callback(element)
    finally:
        if hasattr(aiter, "aclose"):
            await aiter.aclose()
