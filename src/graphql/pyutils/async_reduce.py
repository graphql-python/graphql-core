"""Reduce awaitable values"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Collection, TypeVar, cast

from .is_awaitable import is_awaitable as default_is_awaitable

if TYPE_CHECKING:
    from .awaitable_or_value import AwaitableOrValue

__all__ = ["async_reduce"]

T = TypeVar("T")
U = TypeVar("U")


def async_reduce(
    callback: Callable[[U, T], AwaitableOrValue[U]],
    values: Collection[T],
    initial_value: AwaitableOrValue[U],
    is_awaitable: Callable[[Any], bool] = default_is_awaitable,
) -> AwaitableOrValue[U]:
    """Reduce the given potentially awaitable values using a callback function.

    Similar to functools.reduce(), however the reducing callback may return
    an awaitable, in which case reduction will continue after each promise resolves.

    If the callback does not return an awaitable, then this function will also not
    return an awaitable.
    """
    accumulator: AwaitableOrValue[U] = initial_value
    for value in values:
        if is_awaitable(accumulator):

            async def async_callback(
                current_accumulator: Awaitable[U], current_value: T
            ) -> U:
                result: AwaitableOrValue[U] = callback(
                    await current_accumulator, current_value
                )
                return await result if is_awaitable(result) else result  # type: ignore

            accumulator = async_callback(cast(Awaitable[U], accumulator), value)
        else:
            accumulator = callback(cast(U, accumulator), value)
    return accumulator
