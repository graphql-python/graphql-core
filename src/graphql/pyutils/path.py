"""Path of indices"""

from __future__ import annotations

from typing import Any, NamedTuple, Optional

__all__ = ["Path"]


class Path(NamedTuple):
    """A generic path of string or integer indices"""

    prev: Optional[Path]
    """path with the previous indices"""
    key: str | int
    """current index in the path (string or integer)"""
    typename: str | None
    """name of the parent type to avoid path ambiguity"""

    def add_key(self, key: str | int, typename: str | None = None) -> Path:
        """Return a new Path containing the given key."""
        return Path(self, key, typename)

    def as_list(self) -> list[str | int]:
        """Return a list of the path keys."""
        flattened: list[str | int] = []
        append = flattened.append
        curr: Path = self
        while curr:
            append(curr.key)
            curr = curr.prev
        return flattened[::-1]
