from inspect import isawaitable
from typing import AsyncIterable, Callable

__all__ = ['MapAsyncIterator']


class MapAsyncIterator:
    """Map an AsyncIterable over a callback function.

    Given an AsyncIterable and a callback function, return an AsyncIterator
    which produces values mapped via calling the callback function.

    When the resulting AsyncIterator is closed, the underlying AsyncIterable
    will also be closed.
    """

    def __init__(self, iterable: AsyncIterable, callback: Callable,
                 reject_callback: Callable=None) -> None:
        self.iterator = iterable.__aiter__()
        self.callback = callback
        self.reject_callback = reject_callback
        self.error = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.error is not None:
            raise self.error
        try:
            value = await self.iterator.__anext__()
        except Exception as error:
            if not self.reject_callback or isinstance(error, (
                    StopAsyncIteration, GeneratorExit)):
                raise
            if self.error is not None:
                raise self.error
            result = self.reject_callback(error)
        else:
            if self.error is not None:
                raise self.error
            result = self.callback(value)
        if isawaitable(result):
            result = await result
            if self.error is not None:
                raise self.error
        return result

    async def athrow(self, type_, value=None, traceback=None):
        if self.error:
            return
        athrow = getattr(self.iterator, 'athrow', None)
        if athrow:
            await athrow(type_, value, traceback)
        else:
            error = type_
            if value is not None:
                error = error(value)
                if traceback is not None:
                    error = error.with_traceback(traceback)
            self.error = error

    async def aclose(self):
        if self.error:
            return
        aclose = getattr(self.iterator, 'aclose', None)
        if aclose:
            try:
                await aclose()
            except RuntimeError:
                pass
        else:
            self.error = StopAsyncIteration
