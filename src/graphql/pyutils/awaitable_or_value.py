"""Awaitable or value type"""

from __future__ import annotations

from typing import Awaitable, TypeVar, Union

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias


__all__ = ["AwaitableOrValue"]


T = TypeVar("T")

AwaitableOrValue: TypeAlias = Union[Awaitable[T], T]
