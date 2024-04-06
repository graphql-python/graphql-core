"""GraphQL Syntax Error"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .graphql_error import GraphQLError

if TYPE_CHECKING:
    from ..language.source import Source

__all__ = ["GraphQLSyntaxError"]


class GraphQLSyntaxError(GraphQLError):
    """A GraphQLError representing a syntax error."""

    def __init__(self, source: Source, position: int, description: str) -> None:
        """Initialize the GraphQLSyntaxError"""
        super().__init__(
            f"Syntax Error: {description}", source=source, positions=[position]
        )
        self.description = description
