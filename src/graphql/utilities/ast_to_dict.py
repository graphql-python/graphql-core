"""Python dictionary creation from GraphQL AST"""

from typing import Any, Collection, Dict, List, Optional, overload

from ..language import Node, OperationType
from ..pyutils import is_iterable

__all__ = ["ast_to_dict"]


@overload
def ast_to_dict(
    node: Node, locations: bool = False, cache: Optional[Dict[Node, Any]] = None
) -> Dict: ...


@overload
def ast_to_dict(
    node: Collection[Node],
    locations: bool = False,
    cache: Optional[Dict[Node, Any]] = None,
) -> List[Node]: ...


@overload
def ast_to_dict(
    node: OperationType,
    locations: bool = False,
    cache: Optional[Dict[Node, Any]] = None,
) -> str: ...


def ast_to_dict(
    node: Any, locations: bool = False, cache: Optional[Dict[Node, Any]] = None
) -> Any:
    """Convert a language AST to a nested Python dictionary.

    Set ``locations`` to ``True`` in order to get the locations as well.

    :param node: The AST node (or collection of AST nodes) to convert.
    :param locations: Whether to include the start and end locations of the nodes.
    :param cache: Mapping of already converted nodes, used internally to share the
        dictionaries of nodes that appear multiple times in the AST.
    :returns: A nested dictionary representing the AST.

    >>> from graphql import parse_type, parse_value
    >>> from graphql.utilities import ast_to_dict
    >>> ast_to_dict(parse_type('[String]'))
    {'kind': 'list_type',
     'type': {'kind': 'named_type', 'name': {'kind': 'name', 'value': 'String'}}}
    >>> ast_to_dict(parse_value('42'), locations=True)
    {'kind': 'int_value', 'value': '42', 'loc': {'start': 0, 'end': 2}}
    """
    if isinstance(node, Node):
        if cache is None:
            cache = {}
        elif node in cache:
            return cache[node]
        cache[node] = res = {}
        res.update(
            {
                key: ast_to_dict(getattr(node, key), locations, cache)
                for key in ("kind",) + node.keys[1:]
            }
        )
        if locations:
            loc = node.loc
            if loc:
                res["loc"] = dict(start=loc.start, end=loc.end)
        return res
    if is_iterable(node):
        return [ast_to_dict(sub_node, locations, cache) for sub_node in node]
    if isinstance(node, OperationType):
        return node.value
    return node
