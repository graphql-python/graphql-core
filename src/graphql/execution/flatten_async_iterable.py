from typing import AsyncGenerator, AsyncIterable, TypeVar, Union


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

AsyncIterableOrGenerator = Union[AsyncGenerator[T, None], AsyncIterable[T]]

__all__ = ["flatten_async_iterable"]


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
