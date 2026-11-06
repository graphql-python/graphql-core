"""Source locations"""

import re
from typing import Any, Dict, List, NamedTuple, Sequence, TYPE_CHECKING, Tuple

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

if TYPE_CHECKING:
    from .source import Source  # noqa: F401

__all__ = ["get_location", "get_locations", "SourceLocation", "FormattedSourceLocation"]

_re_newline = re.compile(r"\r\n|[\n\r]")


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
        """Get the location formatted as a dictionary."""
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

    :param source: The source document that contains the position.
    :param position: The UTF-8 character offset in the source body.
    :returns: The 1-indexed line and column for the given source position.

    >>> from graphql.language import Source, get_location
    >>> source = Source('type Query { hello: String }')
    >>> get_location(source, 13)
    SourceLocation(line=1, column=14)
    """
    return source.get_location(position)


def get_locations(locations: Sequence[Tuple["Source", int]]) -> List[SourceLocation]:
    """Get the line and column for several character positions in their sources.

    This scans each of the sources only once.

    For internal use only.

    :meta private:
    """
    if len(locations) < 2:
        return [source.get_location(start) for source, start in locations]
    # Keyed by the id of the source, because sources are compared by value.
    # The values and the given locations keep the sources alive.
    by_source: Dict[int, Tuple["Source", List[Tuple[int, int]]]] = {}
    for index, (source, start) in enumerate(locations):
        by_source.setdefault(id(source), (source, []))[1].append((start, index))
    result: List[Any] = [None] * len(locations)
    for source, positions in by_source.values():
        matches = _re_newline.finditer(source.body)
        match = next(matches, None)
        line = 1
        line_start = 0
        for position, index in sorted(positions):
            while match is not None and match.start() < position:
                line_start = match.end()
                line += 1
                match = next(matches, None)
            result[index] = SourceLocation(line, position + 1 - line_start)
    return result
