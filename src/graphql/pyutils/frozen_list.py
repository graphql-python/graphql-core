from copy import deepcopy
from typing import List, TypeVar, Sequence

from .frozen_error import FrozenError

__all__ = ["FrozenList"]


T = TypeVar("T", covariant=True)

FrozenList = List
