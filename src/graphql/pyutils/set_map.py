"""A Map class keyed by set membership."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, MutableMapping
from collections.abc import Set as AbstractSet
from typing import Any, TypeVar

__all__ = ["SetMap"]

S = TypeVar("S", bound=AbstractSet[Any])
V = TypeVar("V")


class SetMap(MutableMapping[S, V]):
    """Map an order-independent set of member identities to a value.

    Unlike a ``RefMap`` keyed by sets, two sets containing the same members address
    the same entry even when they are different set objects.

    Members are compared by identity, so they do not need to be hashable. The key of
    an entry is the frozen set of the identities of its members. Since every stored
    set keeps its members alive, these identities cannot be reused while the entry
    exists.

    Iteration follows insertion order and returns the first set object stored for
    each key. Key sets must not be mutated after insertion.

    Note that the implementation is limited to what is needed internally.
    """

    # Retains the first set object for each key and preserves insertion order.
    _entries: dict[frozenset[int], tuple[S, V]]

    def __init__(self, items: Iterable[tuple[S, V]] | None = None) -> None:
        super().__init__()
        self._entries = {}
        if items:
            self.update(items)

    @staticmethod
    def _key(members: S) -> frozenset[int]:
        return frozenset(map(id, members))

    def __setitem__(self, members: S, value: V) -> None:
        key = self._key(members)
        entry = self._entries.get(key)
        # Keep the set object that was stored first for this key.
        self._entries[key] = (members if entry is None else entry[0], value)

    def __getitem__(self, members: S) -> V:
        return self._entries[self._key(members)][1]

    def __delitem__(self, members: S) -> None:
        del self._entries[self._key(members)]

    def __contains__(self, members: Any) -> bool:
        return self._key(members) in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self.items())!r})"

    def get(self, members: S, default: Any = None) -> Any:
        """Get the value mapped to the given set of members."""
        entry = self._entries.get(self._key(members))
        return default if entry is None else entry[1]

    def get_or_insert(self, members: S, value: V) -> V:
        """Get the mapped value, inserting the given value if there is none."""
        key = self._key(members)
        entry = self._entries.get(key)
        if entry is not None:
            return entry[1]
        self._entries[key] = (members, value)
        return value

    def get_or_insert_computed(self, members: S, compute_value: Callable[[S], V]) -> V:
        """Get the mapped value, inserting a computed value if there is none."""
        entry = self._entries.get(self._key(members))
        if entry is not None:
            return entry[1]
        value = compute_value(members)
        self[members] = value
        return value

    def __iter__(self) -> Iterator[S]:
        return self.keys()

    def keys(self) -> Iterator[S]:  # type: ignore
        """Return an iterator over the canonical key sets of the map."""
        return (entry[0] for entry in self._entries.values())

    def values(self) -> Iterator[V]:  # type: ignore
        """Return an iterator over the values of the map."""
        return (entry[1] for entry in self._entries.values())

    def items(self) -> Iterator[tuple[S, V]]:  # type: ignore
        """Return an iterator over the key/value-pairs of the map."""
        return iter(self._entries.values())
