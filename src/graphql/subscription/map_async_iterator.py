from asyncio import Event, ensure_future, Future, wait, CancelledError
from concurrent.futures import FIRST_COMPLETED
from inspect import isasyncgen, isawaitable
from typing import cast, Any, AsyncIterable, Callable, Optional, Set, Type, Union
from types import TracebackType

__all__ = ["MapAsyncIterator"]


# noinspection PyAttributeOutsideInit
class MapAsyncIterator:
    """Map an AsyncIterable over a callback function.

    Given an AsyncIterable and a callback function, return an AsyncIterator which
    produces values mapped via calling the callback function.

    When the resulting AsyncIterator is closed, the underlying AsyncIterable will also
    be closed.
    """

    def __init__(
        self,
        iterable: AsyncIterable,
        callback: Callable,
        reject_callback: Optional[Callable] = None,
    ) -> None:
        self.iterator = iterable.__aiter__()
        self.callback = callback
        self.reject_callback = reject_callback
        self._close_event = Event()

    def __aiter__(self) -> "MapAsyncIterator":
        return self

    async def __anext__(self) -> Any:
        if self.is_closed:
            if not isasyncgen(self.iterator):
                raise StopAsyncIteration
            value = await self.iterator.__anext__()
            result = self.callback(value)

        else:
            aclose = ensure_future(self._close_event.wait())
            anext = ensure_future(self.iterator.__anext__())

            # Suppress the StopAsyncIteration exception warning when the
            # iterator is cancelled.
            anext.add_done_callback(lambda *args: anext.exception())
            try:
                pending: Set[Future] = (
                    await wait([aclose, anext], return_when=FIRST_COMPLETED)
                )[1]
            except CancelledError as e:
                # The iterator is cancelled
                aclose.cancel()
                anext.cancel()
                self.is_closed = True
                raise StopAsyncIteration from e

            for task in pending:
                task.cancel()

            if aclose.done():
                raise StopAsyncIteration

            error = anext.exception()
            if error:
                if not self.reject_callback or isinstance(
                    error, (StopAsyncIteration, GeneratorExit)
                ):
                    raise error
                result = self.reject_callback(error)
            else:
                value = anext.result()
                result = self.callback(value)

        return await result if isawaitable(result) else result

    async def athrow(
        self,
        type_: Union[BaseException, Type[BaseException]],
        value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        if not self.is_closed:
            athrow = getattr(self.iterator, "athrow", None)
            if athrow:
                await athrow(type_, value, traceback)
            else:
                await self.aclose()
                if value is None:
                    if traceback is None:
                        raise type_
                    value = (
                        type_
                        if isinstance(value, BaseException)
                        else cast(Type[BaseException], type_)()
                    )
                if traceback is not None:
                    value = value.with_traceback(traceback)
                raise value

    async def aclose(self) -> None:
        if not self.is_closed:
            aclose = getattr(self.iterator, "aclose", None)
            if aclose:
                try:
                    await aclose()
                except RuntimeError:
                    pass
            self.is_closed = True

    @property
    def is_closed(self) -> bool:
        return self._close_event.is_set()

    @is_closed.setter
    def is_closed(self, value: bool) -> None:
        if value:
            self._close_event.set()
        else:
            self._close_event.clear()
