from __future__ import annotations  # Python < 3.10

from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Awaitable,
    Callable,
    TypeVar,
    Union,
)


try:
    from contextlib import aclosing
except ImportError:  # python < 3.10
    from contextlib import asynccontextmanager

    @asynccontextmanager  # type: ignore
    async def aclosing(thing):
        try:
            yield thing
        finally:
            await thing.aclose()


T = TypeVar("T")
V = TypeVar("V")

AsyncIterableOrGenerator = Union[AsyncGenerator[T, None], AsyncIterable[T]]

__all__ = ["flatten_async_iterable", "map_async_iterable"]


async def flatten_async_iterable(
    iterable: AsyncIterableOrGenerator[AsyncIterableOrGenerator[T]],
) -> AsyncGenerator[T, None]:
    """Flatten async iterables.

    Given an AsyncIterable of AsyncIterables, flatten all yielded results into a
    single AsyncIterable.
    """
    async with aclosing(iterable) as sub_iterators:  # type: ignore
        async for sub_iterator in sub_iterators:
            async with aclosing(sub_iterator) as items:  # type: ignore
                async for item in items:
                    yield item


async def map_async_iterable(
    iterable: AsyncIterable[T], callback: Callable[[T], Awaitable[V]]
) -> AsyncGenerator[V, None]:
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
