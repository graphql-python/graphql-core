from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .graphql_error import GraphQLError  # noqa: F401


__all__ = ["format_error"]


def format_error(error: "GraphQLError") -> Dict[str, Any]:
    """Format a GraphQL error.

    Given a GraphQLError, format it according to the rules described by the "Response
    Format, Errors" section of the GraphQL Specification.
    """
    if not error:
        raise TypeError("Received no error object.")
    formatted: Dict[str, Any] = dict(  # noqa: E701 (pycqa/flake8#394)
        message=error.message or "An unknown error occurred.",
        locations=(
            [location.formatted for location in error.locations]
            if error.locations is not None
            else None
        ),
        path=error.path,
    )
    if error.extensions:
        formatted.update(extensions=error.extensions)
    return formatted
