from .location import SourceLocation

__all__ = ["Source"]


class Source:
    """A representation of source input to GraphQL."""

    __slots__ = "body", "name", "location_offset"

    def __init__(
        self, body: str, name: str = None, location_offset: SourceLocation = None
    ) -> None:
        """Initialize source input.


        `name` and `location_offset` are optional. They are useful for clients who
        store GraphQL documents in source files; for example, if the GraphQL input
        starts at line 40 in a file named Foo.graphql, it might be useful for name
        to be "Foo.graphql" and location to be `(40, 0)`.

        line and column in location_offset are 1-indexed
        """

        self.body = body
        self.name = name or "GraphQL request"
        if not location_offset:
            location_offset = SourceLocation(1, 1)
        elif not isinstance(location_offset, SourceLocation):
            # noinspection PyProtectedMember,PyTypeChecker
            location_offset = SourceLocation._make(location_offset)
        if location_offset.line <= 0:
            raise ValueError(
                "line in location_offset is 1-indexed and must be positive"
            )
        if location_offset.column <= 0:
            raise ValueError(
                "column in location_offset is 1-indexed and must be positive"
            )
        self.location_offset = location_offset

    def get_location(self, position: int) -> SourceLocation:
        lines = self.body[:position].splitlines()
        if lines:
            line = len(lines)
            column = len(lines[-1]) + 1
        else:
            line = 1
            column = 1
        return SourceLocation(line, column)

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name!r}>"
