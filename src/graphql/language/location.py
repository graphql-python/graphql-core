"""Source locations"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypedDict

if TYPE_CHECKING:
    from .source import Source

__all__ = ["FormattedSourceLocation", "SourceLocation", "get_location"]


class FormattedSourceLocation(TypedDict):
    """Formatted source location"""

    line: int
    """One-indexed line number in the source document."""
    column: int
    """One-indexed column number in the source document."""


class SourceLocation(NamedTuple):
    """Represents a location in a Source."""

    line: int
    """One-indexed line number in the source document."""
    column: int
    """One-indexed column number in the source document."""

    @property
    def formatted(self) -> FormattedSourceLocation:
        """Get formatted source location."""
        return {"line": self.line, "column": self.column}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self.formatted == other
        return tuple(self) == other

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash((self.line, self.column))


def get_location(source: Source, position: int) -> SourceLocation:
    """Get the line and column for a character position in the source.

    Takes a Source and a UTF-8 character offset, and returns the corresponding line and
    column as a SourceLocation.

    :param source: The source document that contains the position.
    :param position: The UTF-8 character offset in the source body.
    :returns: The 1-indexed line and column for the given source position.

    >>> from graphql.language import Source, get_location
    >>> source = Source('type Query { hello: String }')
    >>> get_location(source, 13)
    SourceLocation(line=1, column=14)
    """
    return source.get_location(position)
