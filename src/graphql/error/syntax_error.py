"""GraphQL Syntax Error"""

from typing import TYPE_CHECKING

from .graphql_error import GraphQLError

if TYPE_CHECKING:
    from ..language.source import Source  # noqa: F401

__all__ = ["GraphQLSyntaxError"]


class GraphQLSyntaxError(GraphQLError):
    """A GraphQLError representing a syntax error.

    Contains useful descriptive information about the syntax error's position in the
    source.

    :param source: The GraphQL source containing the syntax error.
    :param position: Character offset where the syntax error was encountered.
    :param description: Human-readable description of the syntax error.

    >>> from graphql import GraphQLSyntaxError, Source
    >>> error = GraphQLSyntaxError(Source('query {'), 7, 'Expected Name')
    >>> error.message
    'Syntax Error: Expected Name'
    >>> error.locations
    [SourceLocation(line=1, column=8)]
    """

    description: str
    """Human-readable description of the syntax error."""

    def __init__(self, source: "Source", position: int, description: str) -> None:
        super().__init__(
            f"Syntax Error: {description}", source=source, positions=[position]
        )
        self.description = description
