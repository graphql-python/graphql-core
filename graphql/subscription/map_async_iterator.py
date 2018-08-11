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
        self.stop = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.stop:
            raise StopAsyncIteration
        try:
            value = await self.iterator.__anext__()
        except Exception as error:
            if not self.reject_callback or isinstance(error, (
                    StopAsyncIteration, GeneratorExit)):
                raise
            result = self.reject_callback(error)
        else:
            result = self.callback(value)
        if isawaitable(result):
            result = await result
        return result

    async def athrow(self, type_, value=None, traceback=None):
        if self.stop:
            return
        athrow = getattr(self.iterator, 'athrow', None)
        if athrow:
            await athrow(type_, value, traceback)
        else:
            self.stop = True
            if value is None:
                if traceback is None:
                    raise type_
                value = type_()
            if traceback is not None:
                value = value.with_traceback(traceback)
            raise value

    async def aclose(self):
        if self.stop:
            return
        aclose = getattr(self.iterator, 'aclose', None)
        if aclose:
            try:
                await aclose()
            except RuntimeError:
                pass
        else:
            self.stop = True
