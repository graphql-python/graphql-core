"""Grouping function"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

__all__ = ["group_by"]

K = TypeVar("K")
T = TypeVar("T")


def group_by(items: Collection[T], key_fn: Callable[[T], K]) -> dict[K, list[T]]:
    """Group an unsorted collection of items by a key derived via a function."""
    result: dict[K, list[T]] = defaultdict(list)
    for item in items:
        key = key_fn(item)
        result[key].append(item)
    return result
