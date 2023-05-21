from typing import Any, Awaitable, Callable, Collection, TypeVar, cast

from .awaitable_or_value import AwaitableOrValue
from .is_awaitable import is_awaitable as default_is_awaitable


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
                result = callback(await current_accumulator, current_value)
                return await cast(Awaitable, result) if is_awaitable(result) else result

            accumulator = async_callback(cast(Awaitable[U], accumulator), value)
        else:
            accumulator = callback(cast(U, accumulator), value)
    return accumulator
