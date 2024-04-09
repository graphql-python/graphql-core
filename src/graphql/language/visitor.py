"""AST Visitor"""

from __future__ import annotations

from copy import copy
from enum import Enum
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    NamedTuple,
    Optional,
    Tuple,
)

from ..pyutils import inspect, snake_to_camel
from . import ast
from .ast import QUERY_DOCUMENT_KEYS, Node

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias


__all__ = [
    "Visitor",
    "ParallelVisitor",
    "VisitorAction",
    "VisitorKeyMap",
    "visit",
    "BREAK",
    "SKIP",
    "REMOVE",
    "IDLE",
]


class VisitorActionEnum(Enum):
    """Special return values for the visitor methods.

    You can also use the values of this enum directly.
    """

    BREAK = True
    SKIP = False
    REMOVE = Ellipsis


VisitorAction: TypeAlias = Optional[VisitorActionEnum]

# Note that in GraphQL.js these are defined *differently*:
# BREAK = {}, SKIP = false, REMOVE = null, IDLE = undefined

BREAK = VisitorActionEnum.BREAK
SKIP = VisitorActionEnum.SKIP
REMOVE = VisitorActionEnum.REMOVE
IDLE = None

VisitorKeyMap: TypeAlias = Dict[str, Tuple[str, ...]]


class EnterLeaveVisitor(NamedTuple):
    """Visitor with functions for entering and leaving."""

    enter: Callable[..., VisitorAction | None] | None
    leave: Callable[..., VisitorAction | None] | None


class Visitor:
    """Visitor that walks through an AST.

    Visitors can define two generic methods "enter" and "leave". The former will be
    called when a node is entered in the traversal, the latter is called after visiting
    the node and its child nodes. These methods have the following signature::

        def enter(self, node, key, parent, path, ancestors):
            # The return value has the following meaning:
            # IDLE (None): no action
            # SKIP: skip visiting this node
            # BREAK: stop visiting altogether
            # REMOVE: delete this node
            # any other value: replace this node with the returned value
            return

        def leave(self, node, key, parent, path, ancestors):
            # The return value has the following meaning:
            # IDLE (None) or SKIP: no action
            # BREAK: stop visiting altogether
            # REMOVE: delete this node
            # any other value: replace this node with the returned value
            return

    The parameters have the following meaning:

    :arg node: The current node being visiting.
    :arg key: The index or key to this node from the parent node or Array.
    :arg parent: the parent immediately above this node, which may be an Array.
    :arg path: The key path to get to this node from the root node.
    :arg ancestors: All nodes and Arrays visited before reaching parent
        of this node. These correspond to array indices in ``path``.
        Note: ancestors includes arrays which contain the parent of visited node.

    You can also define node kind specific methods by suffixing them with an underscore
    followed by the kind of the node to be visited. For instance, to visit ``field``
    nodes, you would define the methods ``enter_field()`` and/or ``leave_field()``,
    with the same signature as above. If no kind specific method has been defined
    for a given node, the generic method is called.
    """

    # Provide special return values as attributes
    BREAK, SKIP, REMOVE, IDLE = BREAK, SKIP, REMOVE, IDLE

    enter_leave_map: dict[str, EnterLeaveVisitor]

    def __init_subclass__(cls) -> None:
        """Verify that all defined handlers are valid."""
        super().__init_subclass__()
        for attr in cls.__dict__:
            if attr.startswith("_"):
                continue
            attr_kind = attr.split("_", 1)
            if len(attr_kind) < 2:
                kind: str | None = None
            else:
                attr, kind = attr_kind  # noqa: PLW2901
            if attr in ("enter", "leave") and kind:
                name = snake_to_camel(kind) + "Node"
                node_cls = getattr(ast, name, None)
                if (
                    not node_cls
                    or not isinstance(node_cls, type)
                    or not issubclass(node_cls, Node)
                ):
                    msg = f"Invalid AST node kind: {kind}."
                    raise TypeError(msg)

    def __init__(self) -> None:
        self.enter_leave_map = {}

    def get_enter_leave_for_kind(self, kind: str) -> EnterLeaveVisitor:
        """Given a node kind, return the EnterLeaveVisitor for that kind."""
        try:
            return self.enter_leave_map[kind]
        except KeyError:
            enter_fn = getattr(self, f"enter_{kind}", None)
            if not enter_fn:
                enter_fn = getattr(self, "enter", None)
            leave_fn = getattr(self, f"leave_{kind}", None)
            if not leave_fn:
                leave_fn = getattr(self, "leave", None)
            enter_leave = EnterLeaveVisitor(enter_fn, leave_fn)
            self.enter_leave_map[kind] = enter_leave
            return enter_leave


class Stack(NamedTuple):
    """A stack for the visit function."""

    in_array: bool
    idx: int
    keys: tuple[Node, ...]
    edits: list[tuple[int | str, Node]]
    prev: Stack


def visit(
    root: Node, visitor: Visitor, visitor_keys: VisitorKeyMap | None = None
) -> Any:
    """Visit each node in an AST.

    :func:`~.visit` will walk through an AST using a depth-first traversal, calling the
    visitor's enter methods at each node in the traversal, and calling the leave methods
    after visiting that node and all of its child nodes.

    By returning different values from the enter and leave methods, the behavior of the
    visitor can be altered, including skipping over a sub-tree of the AST (by returning
    False), editing the AST by returning a value or None to remove the value, or to stop
    the whole traversal by returning :data:`~.BREAK`.

    When using :func:`~.visit` to edit an AST, the original AST will not be modified,
    and a new version of the AST with the changes applied will be returned from the
    visit function.

    To customize the node attributes to be used for traversal, you can provide a
    dictionary visitor_keys mapping node kinds to node attributes.
    """
    if not isinstance(root, Node):
        msg = f"Not an AST Node: {inspect(root)}."
        raise TypeError(msg)
    if not isinstance(visitor, Visitor):
        msg = f"Not an AST Visitor: {inspect(visitor)}."
        raise TypeError(msg)
    if visitor_keys is None:
        visitor_keys = QUERY_DOCUMENT_KEYS

    stack: Any = None
    in_array = False
    keys: tuple[Node, ...] = (root,)
    idx = -1
    edits: list[Any] = []
    node: Any = root
    key: Any = None
    parent: Any = None
    path: list[Any] = []
    path_append = path.append
    path_pop = path.pop
    ancestors: list[Any] = []
    ancestors_append = ancestors.append
    ancestors_pop = ancestors.pop

    while True:
        idx += 1
        is_leaving = idx == len(keys)
        is_edited = is_leaving and edits
        if is_leaving:
            key = path[-1] if ancestors else None
            node = parent
            parent = ancestors_pop() if ancestors else None
            if is_edited:
                if in_array:
                    node = list(node)
                    edit_offset = 0
                    for edit_key, edit_value in edits:
                        array_key = edit_key - edit_offset
                        if edit_value is REMOVE or edit_value is Ellipsis:
                            node.pop(array_key)
                            edit_offset += 1
                        else:
                            node[array_key] = edit_value
                    node = tuple(node)
                else:
                    node = copy(node)
                    for edit_key, edit_value in edits:
                        setattr(node, edit_key, edit_value)
            idx = stack.idx
            keys = stack.keys
            edits = stack.edits
            in_array = stack.in_array
            stack = stack.prev
        elif parent:
            if in_array:
                key = idx
                node = parent[key]
            else:
                key = keys[idx]
                node = getattr(parent, key, None)
            if node is None:
                continue
            path_append(key)

        if isinstance(node, tuple):
            result = None
        else:
            if not isinstance(node, Node):
                msg = f"Invalid AST Node: {inspect(node)}."
                raise TypeError(msg)
            enter_leave = visitor.get_enter_leave_for_kind(node.kind)
            visit_fn = enter_leave.leave if is_leaving else enter_leave.enter
            if visit_fn:
                result = visit_fn(node, key, parent, path, ancestors)

                if result is BREAK or result is True:
                    break

                if result is SKIP or result is False:
                    if not is_leaving:
                        path_pop()
                        continue

                elif result is not None:
                    edits.append((key, result))
                    if not is_leaving:
                        if isinstance(result, Node):
                            node = result
                        else:
                            path_pop()
                            continue
            else:
                result = None

        if result is None and is_edited:
            edits.append((key, node))

        if is_leaving:
            if path:
                path_pop()
        else:
            stack = Stack(in_array, idx, keys, edits, stack)
            in_array = isinstance(node, tuple)
            keys = node if in_array else visitor_keys.get(node.kind, ())
            idx = -1
            edits = []
            if parent:
                ancestors_append(parent)
            parent = node

        if not stack:
            break

    if edits:
        return edits[-1][1]

    return root


class ParallelVisitor(Visitor):
    """A Visitor which delegates to many visitors to run in parallel.

    Each visitor will be visited for each node before moving on.

    If a prior visitor edits a node, no following visitors will see that node.
    """

    def __init__(self, visitors: Collection[Visitor]) -> None:
        """Create a new visitor from the given list of parallel visitors."""
        super().__init__()
        self.visitors = visitors
        self.skipping: list[Any] = [None] * len(visitors)

    def get_enter_leave_for_kind(self, kind: str) -> EnterLeaveVisitor:
        """Given a node kind, return the EnterLeaveVisitor for that kind."""
        try:
            return self.enter_leave_map[kind]
        except KeyError:
            has_visitor = False
            enter_list: list[Callable[..., VisitorAction | None] | None] = []
            leave_list: list[Callable[..., VisitorAction | None] | None] = []
            for visitor in self.visitors:
                enter, leave = visitor.get_enter_leave_for_kind(kind)
                if not has_visitor and (enter or leave):
                    has_visitor = True
                enter_list.append(enter)
                leave_list.append(leave)

            if has_visitor:

                def enter(node: Node, *args: Any) -> VisitorAction | None:
                    skipping = self.skipping
                    for i, fn in enumerate(enter_list):
                        if not skipping[i] and fn:
                            result = fn(node, *args)
                            if result is SKIP or result is False:
                                skipping[i] = node
                            elif result is BREAK or result is True:
                                skipping[i] = BREAK
                            elif result is not None:
                                return result
                    return None

                def leave(node: Node, *args: Any) -> VisitorAction | None:
                    skipping = self.skipping
                    for i, fn in enumerate(leave_list):
                        if not skipping[i]:
                            if fn:
                                result = fn(node, *args)
                                if result is BREAK or result is True:
                                    skipping[i] = BREAK
                                elif (
                                    result is not None
                                    and result is not SKIP
                                    and result is not False
                                ):
                                    return result
                        elif skipping[i] is node:
                            skipping[i] = None
                    return None

            else:
                enter = leave = None

            enter_leave = EnterLeaveVisitor(enter, leave)
            self.enter_leave_map[kind] = enter_leave
            return enter_leave
