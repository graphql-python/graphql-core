"""Awaitable or value type"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing import TypeAlias


__all__ = ["AwaitableOrValue"]


T = TypeVar("T")

AwaitableOrValue: TypeAlias = Awaitable[T] | T
