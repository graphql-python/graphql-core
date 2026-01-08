"""Check whether objects are iterable"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any, TypeGuard

__all__ = ["is_collection", "is_iterable"]

collection_types: Any = Collection
iterable_types: Any = Iterable
not_iterable_types: Any = (bytearray, bytes, str, memoryview, Mapping)


def is_collection(value: Any) -> TypeGuard[Collection]:
    """Check if value is a collection, but not a string or a mapping."""
    return isinstance(value, collection_types) and not isinstance(
        value, not_iterable_types
    )


def is_iterable(value: Any) -> TypeGuard[Iterable]:
    """Check if value is an iterable, but not a string or a mapping."""
    return isinstance(value, iterable_types) and not isinstance(
        value, not_iterable_types
    )
