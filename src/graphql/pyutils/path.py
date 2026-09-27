"""Path of indices"""

from __future__ import annotations

from typing import NamedTuple

__all__ = ["Path"]


class Path(NamedTuple):
    """A generic path of string or integer indices.

    Represents a linked response path from a field back to the root response.
    """

    prev: Path | None
    """The previous segment in the linked response path, or None at the root."""
    key: str | int
    """The field name or list index for this response path segment."""
    typename: str | None
    """The runtime object type name associated with this path segment, if known."""

    def add_key(self, key: str | int, typename: str | None = None) -> Path:
        """Return a new Path containing the given key.

        :param key: the field name or list index of the new path segment
        :param typename: the runtime object type name of the new path segment,
            if known
        :returns: a new path with this path as its previous segment

        >>> from graphql.pyutils import Path
        >>> path = Path(None, 'viewer', 'Query').add_key('friends', 'User')
        >>> path.key, path.typename, path.prev.key
        ('friends', 'User', 'viewer')
        """
        return Path(self, key, typename)

    def as_list(self) -> list[str | int]:
        """Return a list of the path keys.

        :returns: a list of response path keys from root to leaf

        >>> from graphql.pyutils import Path
        >>> path = Path(None, 'viewer', 'Query').add_key('friends', 'User').add_key(0)
        >>> path.as_list()
        ['viewer', 'friends', 0]
        """
        flattened: list[str | int] = []
        append = flattened.append
        curr: Path | None = self
        while curr:
            append(curr.key)
            curr = curr.prev
        return flattened[::-1]
