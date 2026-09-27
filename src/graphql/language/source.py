from typing import Any

from .location import SourceLocation

__all__ = ["Source", "is_source"]


class Source:
    """A representation of source input to GraphQL.

    The ``name`` and ``location_offset`` parameters are optional, but they are
    useful for clients who store GraphQL documents in source files. For example,
    if the GraphQL input starts at line 40 in a file named ``Foo.graphql``, it might
    be useful for ``name`` to be ``"Foo.graphql"`` and location to be ``(40, 1)``.

    The ``line`` and ``column`` attributes in ``location_offset`` are 1-indexed.

    :param body: The GraphQL source text.
    :param name: Name used in diagnostics for this source.
    :param location_offset: One-indexed line and column where this source begins.

    >>> from graphql.language import Source
    >>> source = Source(
    ...     'type Query { greeting: String }',
    ...     'schema.graphql',
    ...     (10, 1),
    ... )
    >>> source.body
    'type Query { greeting: String }'
    >>> source.name
    'schema.graphql'
    >>> source.location_offset
    SourceLocation(line=10, column=1)
    """

    # allow custom attributes and weak references (not used internally)
    __slots__ = "__weakref__", "__dict__", "body", "name", "location_offset"

    body: str
    """The GraphQL source text."""
    name: str
    """Name used in diagnostics for this source, such as a file path or request name."""
    location_offset: SourceLocation
    """One-indexed line and column where this source begins."""

    def __init__(
        self,
        body: str,
        name: str = "GraphQL request",
        location_offset: SourceLocation = SourceLocation(1, 1),
    ) -> None:
        """Initialize source input."""
        self.body = body
        self.name = name
        if not isinstance(location_offset, SourceLocation):
            location_offset = SourceLocation._make(location_offset)
        if location_offset.line <= 0:
            raise ValueError(
                "line in location_offset is 1-indexed and must be positive."
            )
        if location_offset.column <= 0:
            raise ValueError(
                "column in location_offset is 1-indexed and must be positive."
            )
        self.location_offset = location_offset

    def get_location(self, position: int) -> SourceLocation:
        r"""Get the line and column for a character position in this source.

        :param position: The UTF-8 character offset in the source body.
        :returns: The 1-indexed line and column for the given source position.

        >>> from graphql.language import Source
        >>> Source('type Query {\n  hello: String\n}').get_location(15)
        SourceLocation(line=2, column=3)
        """
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

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, Source) and other.body == self.body) or (
            isinstance(other, str) and other == self.body
        )

    def __ne__(self, other: Any) -> bool:
        return not self == other


def is_source(source: Any) -> bool:
    """Test if the given value is a Source object.

    For internal use only.

    :meta private:
    """
    return isinstance(source, Source)
