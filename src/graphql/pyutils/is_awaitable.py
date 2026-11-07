"""Check whether objects are awaitable"""

from __future__ import annotations

import inspect
from types import GeneratorType
from typing import TYPE_CHECKING, Any, TypeGuard

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable

__all__ = ["is_async_iterable", "is_awaitable"]

CO_ITERABLE_COROUTINE = inspect.CO_ITERABLE_COROUTINE


def is_awaitable(value: Any) -> TypeGuard[Awaitable]:
    """Return True if object can be passed to an ``await`` expression.

    Instead of testing whether the object is an instance of abc.Awaitable, we
    check the existence of an `__await__` attribute. This is much faster.
    Coroutine objects need no extra check, since they all have `__await__`.
    """
    # check for old-style generator based coroutine objects (for Python < 3.11)
    if type(value) is GeneratorType:
        return value.gi_code.co_flags & CO_ITERABLE_COROUTINE != 0
    # check for coroutines and other awaitables (e.g. futures)
    return hasattr(value, "__await__")


def is_async_iterable(value: Any) -> TypeGuard[AsyncIterable]:
    """Return True if object is an asynchronous iterable.

    Instead of testing whether the object is an instance of abc.AsyncIterable, we
    check the existence of an `__aiter__` attribute. This is much faster.
    """
    return hasattr(value, "__aiter__")
