"""GraphQL Error"""

from __future__ import annotations

from sys import exc_info
from typing import TYPE_CHECKING, Any, Collection, Dict

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from ..language.ast import Node
    from ..language.location import (
        FormattedSourceLocation,
        SourceLocation,
    )
    from ..language.source import Source

__all__ = ["GraphQLError", "GraphQLErrorExtensions", "GraphQLFormattedError"]


# Custom extensions
GraphQLErrorExtensions: TypeAlias = Dict[str, Any]
# Use a unique identifier name for your extension, for example the name of
# your library or project. Do not use a shortened identifier as this increases
# the risk of conflicts. We recommend you add at most one extension key,
# a dictionary which can contain all the values you need.


class GraphQLFormattedError(TypedDict, total=False):
    """Formatted GraphQL error"""

    # A short, human-readable summary of the problem that **SHOULD NOT** change
    # from occurrence to occurrence of the problem, except for purposes of localization.
    message: str
    # If an error can be associated to a particular point in the requested
    # GraphQL document, it should contain a list of locations.
    locations: list[FormattedSourceLocation]
    # If an error can be associated to a particular field in the GraphQL result,
    # it _must_ contain an entry with the key `path` that details the path of
    # the response field which experienced the error. This allows clients to
    # identify whether a null result is intentional or caused by a runtime error.
    path: list[str | int]
    # Reserved for implementors to extend the protocol however they see fit,
    # and hence there are no additional restrictions on its contents.
    extensions: GraphQLErrorExtensions


class GraphQLError(Exception):
    """GraphQL Error

    A GraphQLError describes an Error found during the parse, validate, or execute
    phases of performing a GraphQL operation. In addition to a message, it also includes
    information about the locations in a GraphQL document and/or execution result that
    correspond to the Error.
    """

    message: str
    """A message describing the Error for debugging purposes"""

    locations: list[SourceLocation] | None
    """Source locations

    A list of (line, column) locations within the source GraphQL document which
    correspond to this error.

    Errors during validation often contain multiple locations, for example to point out
    two things with the same name. Errors during execution include a single location,
    the field which produced the error.
    """

    path: list[str | int] | None
    """

    A list of field names and array indexes describing the JSON-path into the execution
    response which corresponds to this error.

    Only included for errors during execution.
    """

    nodes: list[Node] | None
    """A list of GraphQL AST Nodes corresponding to this error"""

    source: Source | None
    """The source GraphQL document for the first location of this error

    Note that if this Error represents more than one node, the source may not represent
    nodes after the first node.
    """

    positions: Collection[int] | None
    """Error positions

    A list of character offsets within the source GraphQL document which correspond
    to this error.
    """

    original_error: Exception | None
    """The original error thrown from a field resolver during execution"""

    extensions: GraphQLErrorExtensions | None
    """Extension fields to add to the formatted error"""

    __slots__ = (
        "extensions",
        "locations",
        "message",
        "nodes",
        "original_error",
        "path",
        "positions",
        "source",
    )

    __hash__ = Exception.__hash__

    def __init__(
        self,
        message: str,
        nodes: Collection[Node] | Node | None = None,
        source: Source | None = None,
        positions: Collection[int] | None = None,
        path: Collection[str | int] | None = None,
        original_error: Exception | None = None,
        extensions: GraphQLErrorExtensions | None = None,
    ) -> None:
        """Initialize a GraphQLError."""
        super().__init__(message)
        self.message = message

        if path and not isinstance(path, list):
            path = list(path)
        self.path = path or None  # type: ignore
        self.original_error = original_error

        # Compute list of blame nodes.
        if nodes and not isinstance(nodes, list):
            nodes = [nodes]  # type: ignore
        self.nodes = nodes or None  # type: ignore
        node_locations = (
            [node.loc for node in nodes if node.loc] if nodes else []  # type: ignore
        )

        # Compute locations in the source for the given nodes/positions.
        self.source = source
        if not source and node_locations:
            loc = node_locations[0]
            if loc.source:  # pragma: no branch
                self.source = loc.source
        if not positions and node_locations:
            positions = [loc.start for loc in node_locations]
        self.positions = positions or None
        if positions and source:
            locations: list[SourceLocation] | None = [
                source.get_location(pos) for pos in positions
            ]
        else:
            locations = [loc.source.get_location(loc.start) for loc in node_locations]
        self.locations = locations or None

        if original_error:
            self.__traceback__ = original_error.__traceback__
            if original_error.__cause__:
                self.__cause__ = original_error.__cause__
            elif original_error.__context__:
                self.__context__ = original_error.__context__
            if extensions is None:
                original_extensions = getattr(original_error, "extensions", None)
                if isinstance(original_extensions, dict):
                    extensions = original_extensions
        self.extensions = extensions or {}
        if not self.__traceback__:
            self.__traceback__ = exc_info()[2]

    def __str__(self) -> str:
        # Lazy import to avoid a cyclic dependency between error and language
        from ..language.print_location import print_location, print_source_location

        output = [self.message]

        if self.nodes:
            for node in self.nodes:
                if node.loc:
                    output.append(print_location(node.loc))
        elif self.source and self.locations:
            source = self.source
            for location in self.locations:
                output.append(print_source_location(source, location))

        return "\n\n".join(output)

    def __repr__(self) -> str:
        args = [repr(self.message)]
        if self.locations:
            args.append(f"locations={self.locations!r}")
        if self.path:
            args.append(f"path={self.path!r}")
        if self.extensions:
            args.append(f"extensions={self.extensions!r}")
        return f"{self.__class__.__name__}({', '.join(args)})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, GraphQLError)
            and self.__class__ == other.__class__
            and all(
                getattr(self, slot) == getattr(other, slot)
                for slot in self.__slots__
                if slot != "original_error"
            )
        ) or (
            isinstance(other, dict)
            and "message" in other
            and all(
                slot in self.__slots__ and getattr(self, slot) == other.get(slot)
                for slot in other
                if slot != "original_error"
            )
        )

    def __ne__(self, other: object) -> bool:
        return not self == other

    @property
    def formatted(self) -> GraphQLFormattedError:
        """Get error formatted according to the specification.

        Given a GraphQLError, format it according to the rules described by the
        "Response Format, Errors" section of the GraphQL Specification.
        """
        formatted: GraphQLFormattedError = {
            "message": self.message or "An unknown error occurred.",
        }
        if self.locations is not None:
            formatted["locations"] = [location.formatted for location in self.locations]
        if self.path is not None:
            formatted["path"] = self.path
        if self.extensions:
            formatted["extensions"] = self.extensions
        return formatted
