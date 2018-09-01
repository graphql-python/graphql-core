from asyncio import Event, ensure_future, wait
from concurrent.futures import FIRST_COMPLETED
from inspect import isasyncgen, isawaitable
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
        self._close_event = Event()

    @property
    def closed(self) -> bool:
        return self._close_event.is_set()

    @closed.setter
    def closed(self, value: bool) -> None:
        if value:
            self._close_event.set()
        else:
            self._close_event.clear()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            if not isasyncgen(self.iterator):
                raise StopAsyncIteration
            result = await self.iterator.__anext__()
            return self.callback(result)

        _close = ensure_future(self._close_event.wait())
        _next = ensure_future(self.iterator.__anext__())
        done, pending = await wait(
            [_close, _next],
            return_when=FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        if _close.done():
            raise StopAsyncIteration

        if _next.done():
            error = _next.exception()
            if error:
                if not self.reject_callback or isinstance(error, (
                        StopAsyncIteration, GeneratorExit)):
                    raise error
                result = self.reject_callback(error)
            else:
                result = self.callback(_next.result())

        return (await result) if isawaitable(result) else result

    async def athrow(self, type_, value=None, traceback=None):
        if self.closed:
            return
        athrow = getattr(self.iterator, 'athrow', None)
        if athrow:
            await athrow(type_, value, traceback)
        else:
            self.closed = True
            if value is None:
                if traceback is None:
                    raise type_
                value = type_()
            if traceback is not None:
                value = value.with_traceback(traceback)
            raise value

    async def aclose(self):
        if self.closed:
            return
        aclose = getattr(self.iterator, 'aclose', None)
        if aclose:
            try:
                await aclose()
            except RuntimeError:
                pass
        self.closed = True
