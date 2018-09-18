from typing import Any, Dict, List, Optional, Sequence, Union, TYPE_CHECKING

from .format_error import format_error
from .print_error import print_error

if TYPE_CHECKING:  # pragma: no cover
    from ..language.ast import Node  # noqa
    from ..language.location import SourceLocation  # noqa
    from ..language.source import Source  # noqa

__all__ = ["GraphQLError"]


class GraphQLError(Exception):
    """GraphQL Error

    A GraphQLError describes an Error found during the parse, validate, or
    execute phases of performing a GraphQL operation. In addition to a message,
    it also includes information about the locations in a GraphQL document
    and/or execution result that correspond to the Error.
    """

    message: str
    """A message describing the Error for debugging purposes

    Note: should be treated as readonly, despite invariant usage.
    """

    locations: Optional[List["SourceLocation"]]
    """Source locations

    A list of (line, column) locations within the source
    GraphQL document which correspond to this error.

    Errors during validation often contain multiple locations, for example
    to point out two things with the same name. Errors during execution
    include a single location, the field which produced the error.
    """

    path: Optional[List[Union[str, int]]]
    """A list of GraphQL AST Nodes corresponding to this error"""

    nodes: Optional[List["Node"]]
    """The source GraphQL document for the first location of this error

    Note that if this Error represents more than one node, the source
    may not represent nodes after the first node.
    """

    source: Optional["Source"]
    """The source GraphQL document for the first location of this error

    Note that if this Error represents more than one node, the source may
    not represent nodes after the first node.
    """

    positions: Optional[Sequence[int]]
    """Error positions

    A list of character offsets within the source GraphQL document
    which correspond to this error.
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

    def __init__(
        self,
        message: str,
        nodes: Union[Sequence["Node"], "Node"] = None,
        source: "Source" = None,
        positions: Sequence[int] = None,
        path: Sequence[Union[str, int]] = None,
        original_error: Exception = None,
        extensions: Dict[str, Any] = None,
    ) -> None:
        super(GraphQLError, self).__init__(message)
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
        if not extensions and original_error:
            try:
                extensions = original_error.extensions  # type: ignore
            except AttributeError:
                pass
        self.extensions = extensions or {}

    def __str__(self):
        return print_error(self)

    def __repr__(self):
        args = [repr(self.message)]
        if self.locations:
            args.append(f"locations={self.locations!r}")
        if self.path:
            args.append(f"path={self.path!r}")
        if self.extensions:
            args.append(f"extensions={self.extensions!r}")
        return f"{self.__class__.__name__}({', '.join(args)})"

    def __eq__(self, other):
        return (
            isinstance(other, GraphQLError)
            and self.__class__ == other.__class__
            and all(
                getattr(self, slot) == getattr(other, slot) for slot in self.__slots__
            )
        ) or (
            isinstance(other, dict)
            and "message" in other
            and all(
                slot in self.__slots__ and getattr(self, slot) == other.get(slot)
                for slot in other
            )
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def formatted(self):
        """Get error formatted according to the specification."""
        return format_error(self)
