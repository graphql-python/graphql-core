"""Helpers for async iterables"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, suppress
from typing import Generic, TypeVar

__all__ = ["aclosing", "map_async_iterable"]

T = TypeVar("T")
V = TypeVar("V")

AsyncIterableOrGenerator = AsyncGenerator[T, None] | AsyncIterable[T]

suppress_exceptions = suppress(Exception)


class aclosing(AbstractAsyncContextManager, Generic[T]):  # noqa: N801
    """Async context manager for safely finalizing an async iterator or generator.

    Contrary to the function available via the standard library, this one silently
    ignores the case that custom iterators have no aclose() method.
    """

    def __init__(self, iterable: AsyncIterableOrGenerator[T]) -> None:
        self.iterable = iterable

    async def __aenter__(self) -> AsyncIterableOrGenerator[T]:
        return self.iterable

    async def __aexit__(self, *_exc_info: object) -> None:
        try:
            aclose = self.iterable.aclose  # type: ignore
        except AttributeError:
            pass  # do not complain if the iterator has no aclose() method
        else:
            with suppress_exceptions:  # or if the aclose() method fails
                await aclose()


async def map_async_iterable(
    iterable: AsyncIterableOrGenerator[T], callback: Callable[[T], Awaitable[V]]
) -> AsyncGenerator[V, None]:
    """Map an AsyncIterable over a callback function.

    Given an AsyncIterable and an async callback function, return an AsyncGenerator
    that produces values mapped via calling the callback function.
    If the inner iterator supports an ``aclose()`` method, it will be called when
    the generator finishes or closes.

    :param iterable: The source AsyncIterable whose values shall be mapped.
    :param callback: The async function that is called with each source value.
    :returns: An AsyncGenerator yielding the mapped values.

    >>> import asyncio
    >>> from graphql import map_async_iterable
    >>> async def numbers():
    ...     for number in range(3):
    ...         yield number
    >>> async def double(number):
    ...     return 2 * number
    >>> async def doubled_numbers():
    ...     return [value async for value in map_async_iterable(numbers(), double)]
    >>> asyncio.run(doubled_numbers())
    [0, 2, 4]
    """
    async with aclosing(iterable) as items:
        async for item in items:
            yield await callback(item)
