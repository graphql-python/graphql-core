from copy import deepcopy
from typing import List, TypeVar, Tuple

from .frozen_error import FrozenError

__all__ = ["FrozenList"]


T = TypeVar("T", covariant=True)


class FrozenList(Tuple[T, ...]):
    """List that can only be read, but not changed."""
