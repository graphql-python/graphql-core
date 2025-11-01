"""Boxed Awaitable or Value"""

from __future__ import annotations

from asyncio import CancelledError, Future, ensure_future, isfuture
from contextlib import suppress
from typing import Awaitable, Generic, TypeVar

__all__ = ["BoxedAwaitableOrValue"]

T = TypeVar("T")


class BoxedAwaitableOrValue(Generic[T]):
    """Container for an Awaitable or a Value that updates itself.

    A BoxedAwaitableOrValue is a container for a value or Awaitable where the value
    will be updated when the Awaitable has been awaited.
    """

    __slots__ = "_future", "_value"

    _value: T | Future[T]

    def __init__(self, value: T | Awaitable[T]) -> None:
        """Initialize the BoxedAwaitableOrValue with the given value or Awaitable."""
        try:
            value = ensure_future(value)  # type: ignore
        except TypeError:
            pass
        else:
            value.add_done_callback(self._update_value)
        self._value = value  # type: ignore

    @property
    def value(self) -> T:
        """Get the current value."""
        value = self._value
        if isfuture(value) and value.done():
            self._value = value = value.result()
        return value  # type: ignore

    def _update_value(self, value: Future[T]) -> None:
        """Update the boxed value when the Awaitable is done."""
        with suppress(CancelledError):
            self._value = value.result()
