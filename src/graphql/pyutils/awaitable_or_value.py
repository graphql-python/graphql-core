"""Awaitable or value type"""

from __future__ import annotations

from typing import Awaitable, TypeAlias, TypeVar, Union

__all__ = ["AwaitableOrValue"]


T = TypeVar("T")

AwaitableOrValue: TypeAlias = Union[Awaitable[T], T]
