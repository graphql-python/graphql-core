from .graphql_error import GraphQLError

__all__ = ["GraphQLSyntaxError"]


class GraphQLSyntaxError(GraphQLError):
    """A GraphQLError representing a syntax error."""

    def __init__(self, source, position, description):
        super().__init__(
            f"Syntax Error: {description}", source=source, positions=[position]
        )
        self.description = description
