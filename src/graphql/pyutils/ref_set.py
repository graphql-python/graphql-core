"""A Set class that work similar to JavaScript."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableSet
from contextlib import suppress
from typing import Any, TypeVar

from .ref_map import RefMap

__all__ = ["RefSet"]


T = TypeVar("T")


class RefSet(MutableSet[T]):
    """A set like object that allows mutable objects as elements.

    This class keeps the insertion order unlike a normal set.

    Note that the implementation is limited to what is needed internally.
    """

    _map: RefMap[T, None]

    def __init__(self, values: Iterable[T] | None = None) -> None:
        super().__init__()
        self._map = RefMap()
        if values:
            self.update(values)

    def __contains__(self, key: Any) -> bool:
        return key in self._map

    def __iter__(self) -> Iterator[T]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self)!r})"

    def add(self, value: T) -> None:
        """Add the given item to the set."""
        self._map[value] = None

    def remove(self, value: T) -> None:
        """Remove the given item from the set."""
        del self._map[value]

    def discard(self, value: T) -> None:
        """Remove the given item from the set if it exists."""
        with suppress(KeyError):
            self.remove(value)

    def update(self, values: Iterable[T] | None = None) -> None:
        """Update the set with the given items."""
        if values:
            for item in values:
                self.add(item)
