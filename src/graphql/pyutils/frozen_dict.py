from copy import deepcopy
from typing import Dict, TypeVar

from .frozen_error import FrozenError

__all__ = ["FrozenDict"]

K = TypeVar("K")
T = TypeVar("T", covariant=True)


class FrozenDict(Dict[K, T]):
    """Dictionary that can only be read, but not changed."""

    def __delitem__(self, key):
        raise FrozenError

    def __setitem__(self, key, value):
        raise FrozenError

    def __iadd__(self, value):
        raise FrozenError

    def __hash__(self):
        return hash(tuple(self.items()))

    def __copy__(self):
        return FrozenDict(self)

    copy = __copy__

    def __deepcopy__(self, memo):
        return FrozenDict({k: deepcopy(v, memo) for k, v in self.items()})

    def clear(self):
        raise FrozenError

    def pop(self, key, default=None):
        raise FrozenError

    def popitem(self):
        raise FrozenError

    def setdefault(self, key, default=None):
        raise FrozenError

    def update(self, other=None):
        raise FrozenError
