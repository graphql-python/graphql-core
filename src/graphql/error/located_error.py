"""Located GraphQL Error"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Collection

from ..pyutils import inspect
from .graphql_error import GraphQLError

if TYPE_CHECKING:
    from ..language.ast import Node

__all__ = ["located_error"]


def located_error(
    original_error: Exception,
    nodes: None | Collection[Node] = None,
    path: Collection[str | int] | None = None,
) -> GraphQLError:
    """Located GraphQL Error

    Given an arbitrary Exception, presumably thrown while attempting to execute a
    GraphQL operation, produce a new GraphQLError aware of the location in the document
    responsible for the original Exception.
    """
    # Sometimes a non-error is thrown, wrap it as a TypeError to ensure consistency.
    if not isinstance(original_error, Exception):
        original_error = TypeError(f"Unexpected error value: {inspect(original_error)}")
    # Note: this uses a brand-check to support GraphQL errors originating from
    # other contexts.
    if isinstance(original_error, GraphQLError) and original_error.path is not None:
        return original_error
    try:
        message = str(original_error.message)  # type: ignore
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

    with suppress(AttributeError):
        nodes = original_error.nodes or nodes  # type: ignore
    return GraphQLError(message, nodes, source, positions, path, original_error)
