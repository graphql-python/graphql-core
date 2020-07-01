from typing import Any, Dict, NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .source import Source  # noqa: F401

__all__ = ["get_location", "SourceLocation"]


class SourceLocation(NamedTuple):
    """Represents a location in a Source."""

    line: int
    column: int

    @property
    def formatted(self) -> Dict[str, int]:
        return dict(line=self.line, column=self.column)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, dict):
            return self.formatted == other
        return tuple(self) == other

    def __ne__(self, other: Any) -> bool:
        return not self == other


def get_location(source: "Source", position: int) -> SourceLocation:
    """Get the line and column for a character position in the source.

    Takes a Source and a UTF-8 character offset, and returns the corresponding line and
    column as a SourceLocation.
    """
    return source.get_location(position)
