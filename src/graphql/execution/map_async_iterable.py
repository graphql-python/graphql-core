from __future__ import annotations  # Python < 3.10

from types import TracebackType
from typing import Any, AsyncIterable, Awaitable, Callable, Optional, Type, Union


__all__ = ["MapAsyncIterable"]


# The following is a class because its type is checked in the code.
# otherwise, it could be implemented as a simple async generator function


# noinspection PyAttributeOutsideInit
class MapAsyncIterable:
    """Map an AsyncIterable over a callback function.

    Given an AsyncIterable and a callback function, return an AsyncIterator which
    produces values mapped via calling the callback async function.

    Similar to an AsyncGenerator, an `aclose()` method is provivde which
    will close the underlying AsyncIterable be if it has an `aclose()` method.
    """

    def __init__(
        self, iterable: AsyncIterable[Any], callback: Callable[[Any], Awaitable[Any]]
    ) -> None:
        self.iterator = iterable.__aiter__()
        self.callback = callback
        self._ageniter = self._agen()
        self.is_closed = False  # used by unittests

    def __aiter__(self) -> MapAsyncIterable:
        """Get the iterator object."""
        return self

    async def __anext__(self) -> Any:
        """Get the next value of the iterator."""
        return await self._ageniter.__anext__()

    async def _agen(self) -> Any:
        try:
            async for v in self.iterator:
                yield await self.callback(v)
        finally:
            self.is_closed = True
            if hasattr(self.iterator, "aclose"):
                await self.iterator.aclose()

    # This is not a standard method and is only used in unittests.  Should be removed.
    async def athrow(
        self,
        type_: Union[BaseException, Type[BaseException]],
        value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        """Throw an exception into the asynchronous iterator."""
        await self._ageniter.athrow(type_, value, traceback)

    async def aclose(self) -> None:
        """Close the iterator."""
        await self._ageniter.aclose()
