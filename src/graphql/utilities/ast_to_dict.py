"""Python dictionary creation from GraphQL AST"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from ..language import Node, OperationType
from ..pyutils import is_iterable

if TYPE_CHECKING:
    from collections.abc import Collection

__all__ = ["ast_to_dict"]


@overload
def ast_to_dict(
    node: Node, locations: bool = False, cache: dict[Node, Any] | None = None
) -> dict: ...


@overload
def ast_to_dict(
    node: Collection[Node],
    locations: bool = False,
    cache: dict[Node, Any] | None = None,
) -> list[Node]: ...


@overload
def ast_to_dict(
    node: OperationType,
    locations: bool = False,
    cache: dict[Node, Any] | None = None,
) -> str: ...


def ast_to_dict(
    node: Any, locations: bool = False, cache: dict[Node, Any] | None = None
) -> Any:
    """Convert a language AST to a nested Python dictionary.

    Set `locations` to True in order to get the locations as well.
    """
    if isinstance(node, Node):
        if cache is None:
            cache = {}
        elif node in cache:
            return cache[node]
        cache[node] = res = {}
        # Note: We don't use msgspec.structs.asdict() because loc needs special
        # handling (converted to {start, end} dict rather than full Location object)
        # Filter out 'loc' - it's handled separately for the locations option
        fields = [f for f in node.keys if f != "loc"]
        res.update(
            {
                key: ast_to_dict(getattr(node, key), locations, cache)
                for key in ("kind", *fields)
            }
        )
        if locations:
            loc = getattr(node, "loc", None)
            if loc:
                res["loc"] = {"start": loc.start, "end": loc.end}
        return res
    if is_iterable(node):
        return [ast_to_dict(sub_node, locations, cache) for sub_node in node]
    if isinstance(node, OperationType):
        return node.value
    return node
