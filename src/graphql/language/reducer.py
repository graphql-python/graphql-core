"""AST reducer"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..pyutils import inspect
from .ast import QUERY_DOCUMENT_KEYS, Node

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ["ReducedNode", "reduce"]


class ReducedNode:
    """A copy of an AST node with its children replaced by their reduced values."""


def reduce(root: Node, reducer: Mapping[str, Callable[[Any], Any]]) -> Any:
    """Reduce children before their parents without changing the input AST.

    Missing callbacks produce ``None``; returned values are not revisited.

    For internal use only.

    :param root: The AST node to reduce.
    :param reducer: Callbacks by node kind, receiving nodes with their children reduced.
    :returns: The reduced root value, or ``None`` if it has no callback.

    :meta private:
    """
    if not isinstance(root, Node):
        msg = f"Not an AST Node: {inspect(root)}."
        raise TypeError(msg)
    document_keys = QUERY_DOCUMENT_KEYS
    get_callback = reducer.get
    stack: list[tuple[Any, tuple[str, ...] | None, Any, int]] = []
    push = stack.append
    pop = stack.pop
    parent: Any = (root,)
    keys: tuple[str, ...] | None = None
    results: Any = []
    index = -1

    while True:
        kind: str | None = None
        index += 1
        if index == (len(parent) if keys is None else len(keys)):
            node: Any = results
            if keys is not None:
                kind = parent.kind
            parent, keys, results, index = pop()
        else:
            node = parent[index] if keys is None else getattr(parent, keys[index])
            if node is None:
                continue
            if isinstance(node, (list, tuple)):
                if node:
                    push((parent, keys, results, index))
                    parent, keys, results, index = node, None, [], -1
                    continue
            elif isinstance(node, Node):
                kind = node.kind
                node_keys = document_keys.get(kind)
                if node_keys:
                    push((parent, keys, results, index))
                    results = ReducedNode()
                    results.__dict__.update(node.__dict__)
                    parent, keys, index = node, node_keys, -1
                    continue
            else:
                msg = f"Invalid AST Node: {inspect(node)}."
                raise TypeError(msg)
        if kind is not None:
            callback = get_callback(kind)
            node = callback(node) if callback else None
        if keys is None:
            results.append(node)
        else:
            setattr(results, keys[index], node)
        if not stack:
            return node
