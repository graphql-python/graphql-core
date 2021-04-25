from sys import exc_info
from typing import Any, Collection, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..language.ast import Node  # noqa: F401
    from ..language.location import SourceLocation  # noqa: F401
    from ..language.source import Source  # noqa: F401

__all__ = ["GraphQLError", "format_error", "print_error"]


class GraphQLError(Exception):
    """GraphQL Error

    A GraphQLError describes an Error found during the parse, validate, or execute
    phases of performing a GraphQL operation. In addition to a message, it also includes
    information about the locations in a GraphQL document and/or execution result that
    correspond to the Error.
    """

    message: str
    """A message describing the Error for debugging purposes

    Note: should be treated as readonly, despite invariant usage.
    """

    locations: Optional[List["SourceLocation"]]
    """Source locations

    A list of (line, column) locations within the source GraphQL document which
    correspond to this error.

    Errors during validation often contain multiple locations, for example to point out
    two things with the same name. Errors during execution include a single location,
    the field which produced the error.
    """

    path: Optional[List[Union[str, int]]]
    """

    A list of field names and array indexes describing the JSON-path into the execution
    response which corresponds to this error.

    Only included for errors during execution.
    """

    nodes: Optional[List["Node"]]
    """A list of GraphQL AST Nodes corresponding to this error"""

    source: Optional["Source"]
    """The source GraphQL document for the first location of this error

    Note that if this Error represents more than one node, the source may not represent
    nodes after the first node.
    """

    positions: Optional[Collection[int]]
    """Error positions

    A list of character offsets within the source GraphQL document which correspond
    to this error.
    """

    original_error: Optional[Exception]
    """The original error thrown from a field resolver during execution"""

    extensions: Optional[Dict[str, Any]]
    """Extension fields to add to the formatted error"""

    __slots__ = (
        "message",
        "nodes",
        "source",
        "positions",
        "locations",
        "path",
        "original_error",
        "extensions",
    )

    __hash__ = Exception.__hash__

    def __init__(
        self,
        message: str,
        nodes: Union[Collection["Node"], "Node", None] = None,
        source: Optional["Source"] = None,
        positions: Optional[Collection[int]] = None,
        path: Optional[Collection[Union[str, int]]] = None,
        original_error: Optional[Exception] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if nodes and not isinstance(nodes, list):
            nodes = [nodes]  # type: ignore
        self.nodes = nodes or None  # type: ignore
        self.source = source
        if not source and nodes:
            node = nodes[0]  # type: ignore
            if node and node.loc and node.loc.source:
                self.source = node.loc.source
        if not positions and nodes:
            positions = [node.loc.start for node in nodes if node.loc]  # type: ignore
        self.positions = positions or None
        if positions and source:
            locations: Optional[List["SourceLocation"]] = [
                source.get_location(pos) for pos in positions
            ]
        elif nodes:
            locations = [
                node.loc.source.get_location(node.loc.start)
                for node in nodes  # type: ignore
                if node.loc
            ]
        else:
            locations = None
        self.locations = locations
        if path and not isinstance(path, list):
            path = list(path)
        self.path = path or None  # type: ignore
        self.original_error = original_error
        if original_error:
            self.__traceback__ = original_error.__traceback__
            if original_error.__cause__:
                self.__cause__ = original_error.__cause__
            elif original_error.__context__:
                self.__context__ = original_error.__context__
            if not extensions:
                try:
                    # noinspection PyUnresolvedReferences
                    extensions = original_error.extensions  # type: ignore
                except AttributeError:
                    pass
        self.extensions = extensions or {}
        if not self.__traceback__:
            self.__traceback__ = exc_info()[2]

    def __str__(self) -> str:
        return print_error(self)

    def __repr__(self) -> str:
        args = [repr(self.message)]
        if self.locations:
            args.append(f"locations={self.locations!r}")
        if self.path:
            args.append(f"path={self.path!r}")
        if self.extensions:
            args.append(f"extensions={self.extensions!r}")
        return f"{self.__class__.__name__}({', '.join(args)})"

    def __eq__(self, other: Any) -> bool:
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

    def __ne__(self, other: Any) -> bool:
        return not self == other

    @property
    def formatted(self) -> Dict[str, Any]:
        """Get error formatted according to the specification."""
        return format_error(self)


def print_error(error: GraphQLError) -> str:
    """Print a GraphQLError to a string.

    Represents useful location information about the error's position in the source.
    """
    # Lazy import to avoid a cyclic dependency between error and language
    from ..language.print_location import print_location, print_source_location

    output = [error.message]

    if error.nodes:
        for node in error.nodes:
            if node.loc:
                output.append(print_location(node.loc))
    elif error.source and error.locations:
        source = error.source
        for location in error.locations:
            output.append(print_source_location(source, location))

    return "\n\n".join(output)


def format_error(error: GraphQLError) -> Dict[str, Any]:
    """Format a GraphQL error.

    Given a GraphQLError, format it according to the rules described by the "Response
    Format, Errors" section of the GraphQL Specification.
    """
    if not isinstance(error, GraphQLError):
        raise TypeError("Expected a GraphQLError.")
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
