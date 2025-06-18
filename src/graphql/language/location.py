"""Source locations"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

if TYPE_CHECKING:
    from .source import Source

__all__ = ["FormattedSourceLocation", "SourceLocation", "get_location"]


class FormattedSourceLocation(TypedDict):
    """Formatted source location"""

    line: int
    column: int


class SourceLocation(NamedTuple):
    """Represents a location in a Source."""

    line: int
    column: int

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
    """
    return source.get_location(position)
