from typing import TYPE_CHECKING, Sequence, Union

from .graphql_error import GraphQLError

if TYPE_CHECKING:  # pragma: no cover
    from ..language.ast import Node  # noqa: F401

__all__ = ["located_error"]


def located_error(
    original_error: Union[Exception, GraphQLError],
    nodes: Sequence["Node"],
    path: Sequence[Union[str, int]],
) -> GraphQLError:
    """Located GraphQL Error

    Given an arbitrary Error, presumably thrown while attempting to execute a GraphQL
    operation, produce a new GraphQLError aware of the location in the document
    responsible for the original Error.
    """
    if original_error:
        # Note: this uses a brand-check to support GraphQL errors originating from
        # other contexts.
        try:
            if isinstance(original_error.path, list):  # type: ignore
                return original_error  # type: ignore
        except AttributeError:
            pass
    try:
        message = original_error.message  # type: ignore
    except AttributeError:
        message = str(original_error)
    try:
        source = original_error.source  # type: ignore
    except AttributeError:
        source = None
    try:
        positions = original_error.positions  # type: ignore
    except AttributeError:
        positions = None
    try:
        nodes = original_error.nodes or nodes  # type: ignore
    except AttributeError:
        pass
    return GraphQLError(message, nodes, source, positions, path, original_error)
