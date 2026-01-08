"""Awaitable or value type"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeAlias, TypeVar

__all__ = ["AwaitableOrValue"]


T = TypeVar("T")

AwaitableOrValue: TypeAlias = Awaitable[T] | T
