from typing import TypeVar, Tuple

__all__ = ["FrozenList"]


T = TypeVar("T", covariant=True)


class FrozenList(Tuple[T, ...]):
    """List that can only be read, but not changed."""
