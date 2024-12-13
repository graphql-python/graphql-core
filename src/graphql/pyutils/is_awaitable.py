"""Check whether objects are awaitable"""

from __future__ import annotations

import inspect
from types import CoroutineType, GeneratorType
from typing import Any, Awaitable

try:
    from typing import TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeGuard


__all__ = ["is_awaitable"]

CO_ITERABLE_COROUTINE = inspect.CO_ITERABLE_COROUTINE

_common_primitives = {int, float, bool, str, list, dict, tuple, type(None)}


def is_awaitable(value: Any) -> TypeGuard[Awaitable]:
    """Return True if object can be passed to an ``await`` expression.

    Instead of testing whether the object is an instance of abc.Awaitable, we
    check the existence of an `__await__` attribute. This is much faster.
    """
    if type(value) in _common_primitives:
        return False

    return (
        # check for coroutine objects
        isinstance(value, CoroutineType)
        # check for old-style generator based coroutine objects
        or isinstance(value, GeneratorType)  # for Python < 3.11
        and bool(value.gi_code.co_flags & CO_ITERABLE_COROUTINE)
        # check for other awaitables (e.g. futures)
        or hasattr(value, "__await__")
    )
