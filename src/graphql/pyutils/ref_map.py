"""A Map class that work similar to JavaScript."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableMapping
from typing import Any, TypeVar

__all__ = ["RefMap"]

K = TypeVar("K")
V = TypeVar("V")


class RefMap(MutableMapping[K, V]):
    """A dictionary like object that allows mutable objects as keys.

    This class keeps the insertion order like a normal dictionary.

    Note that the implementation is limited to what is needed internally.
    """

    _map: dict[int, tuple[K, V]]

    def __init__(self, items: Iterable[tuple[K, V]] | None = None) -> None:
        super().__init__()
        self._map = {}
        if items:
            self.update(items)

    def __setitem__(self, key: K, value: V) -> None:
        self._map[id(key)] = (key, value)

    def __getitem__(self, key: K) -> Any:
        return self._map[id(key)][1]

    def __delitem__(self, key: K) -> None:
        del self._map[id(key)]

    def __contains__(self, key: Any) -> bool:
        return id(key) in self._map

    def __len__(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self.items())!r})"

    def get(self, key: Any, default: Any = None) -> Any:
        """Get the mapped value for the given key."""
        try:
            return self._map[id(key)][1]
        except KeyError:
            return default

    def __iter__(self) -> Iterator[K]:
        return self.keys()

    def keys(self) -> Iterator[K]:  # type: ignore
        """Return an iterator over the keys of the map."""
        return (item[0] for item in self._map.values())

    def values(self) -> Iterator[V]:  # type: ignore
        """Return an iterator over the values of the map."""
        return (item[1] for item in self._map.values())

    def items(self) -> Iterator[tuple[K, V]]:  # type: ignore
        """Return an iterator over the key/value-pairs of the map."""
        return self._map.values()  # type: ignore

    def update(self, items: Iterable[tuple[K, V]] | None = None) -> None:  # type: ignore
        """Update the map with the given key/value-pairs."""
        if items:
            for key, value in items:
                self[key] = value
