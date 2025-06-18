"""GraphQL source input"""

from __future__ import annotations

from typing import Any

from .location import SourceLocation

try:
    from typing import TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeGuard

__all__ = ["Source", "is_source"]

DEFAULT_NAME = "GraphQL request"
DEFAULT_SOURCE_LOCATION = SourceLocation(1, 1)


class Source:
    """A representation of source input to GraphQL."""

    # allow custom attributes and weak references (not used internally)
    __slots__ = "__dict__", "__weakref__", "body", "location_offset", "name"

    def __init__(
        self,
        body: str,
        name: str = DEFAULT_NAME,
        location_offset: SourceLocation = DEFAULT_SOURCE_LOCATION,
    ) -> None:
        """Initialize source input.

        The ``name`` and ``location_offset`` parameters are optional, but they are
        useful for clients who store GraphQL documents in source files. For example,
        if the GraphQL input starts at line 40 in a file named ``Foo.graphql``, it might
        be useful for ``name`` to be ``"Foo.graphql"`` and location to be ``(40, 0)``.

        The ``line`` and ``column`` attributes in ``location_offset`` are 1-indexed.
        """
        self.body = body
        self.name = name
        if not isinstance(location_offset, SourceLocation):
            location_offset = SourceLocation._make(location_offset)
        if location_offset.line <= 0:
            msg = "line in location_offset is 1-indexed and must be positive."
            raise ValueError(msg)
        if location_offset.column <= 0:
            msg = "column in location_offset is 1-indexed and must be positive."
            raise ValueError(msg)
        self.location_offset = location_offset

    def get_location(self, position: int) -> SourceLocation:
        """Get source location."""
        lines = self.body[:position].splitlines()
        if lines:
            line = len(lines)
            column = len(lines[-1]) + 1
        else:
            line = 1
            column = 1
        return SourceLocation(line, column)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Source) and other.body == self.body) or (
            isinstance(other, str) and other == self.body
        )

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(self.body)


def is_source(source: Any) -> TypeGuard[Source]:
    """Test if the given value is a Source object.

    For internal use only.
    """
    return isinstance(source, Source)
