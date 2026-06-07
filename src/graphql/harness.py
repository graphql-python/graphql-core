"""The parse/validate/execute/subscribe harness used by ``graphql``."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, NamedTuple

from .execution import execute, subscribe
from .language import parse
from .validation import validate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from .error import GraphQLError
    from .execution import ExecutionResult
    from .language import DocumentNode
    from .pyutils import AwaitableOrValue

__all__ = [
    "GraphQLExecuteFn",
    "GraphQLHarness",
    "GraphQLParseFn",
    "GraphQLSubscribeFn",
    "GraphQLValidateFn",
    "default_harness",
]

# The functions which make up the harness purposefully expose maybe-async return
# types, even though the internal parse and validate functions are always sync, to
# encourage servers and other tooling to expect that user-supplied versions of these
# functions may have async pre/post hooks.
GraphQLParseFn = Callable[..., "AwaitableOrValue[DocumentNode]"]
GraphQLValidateFn = Callable[..., "AwaitableOrValue[list[GraphQLError]]"]
GraphQLExecuteFn = Callable[..., "AwaitableOrValue[ExecutionResult]"]
GraphQLSubscribeFn = Callable[
    ..., "AwaitableOrValue[AsyncIterator[ExecutionResult] | ExecutionResult]"
]


class GraphQLHarness(NamedTuple):
    """The set of functions used by ``graphql`` to fulfill an operation.

    A custom harness can be passed to ``graphql`` to supply user-defined versions of
    these functions, enabling a simple API for adding pre/post hooks. Replace
    individual functions with :meth:`~typing.NamedTuple._replace`, e.g.
    ``default_harness._replace(execute=my_execute)``.
    """

    parse: GraphQLParseFn
    validate: GraphQLValidateFn
    execute: GraphQLExecuteFn
    subscribe: GraphQLSubscribeFn


default_harness = GraphQLHarness(
    parse=parse,
    validate=validate,
    execute=execute,
    subscribe=subscribe,
)
"""The default parse/validate/execute/subscribe harness used by ``graphql``."""
