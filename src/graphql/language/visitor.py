from copy import copy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    NamedTuple,
    Sequence,
    Tuple,
    Union,
)

from ..pyutils import inspect, snake_to_camel
from . import ast

from .ast import Node

if TYPE_CHECKING:  # pragma: no cover
    from ..utilities import TypeInfo  # noqa: F401

__all__ = [
    "Visitor",
    "ParallelVisitor",
    "TypeInfoVisitor",
    "visit",
    "BREAK",
    "SKIP",
    "REMOVE",
    "IDLE",
]


# Special return values for the visitor methods:
# Note that in GraphQL.js these are defined differently:
# BREAK = {}, SKIP = false, REMOVE = null, IDLE = undefined
BREAK, SKIP, REMOVE, IDLE = True, False, Ellipsis, None

# Default map from visitor kinds to their traversable node attributes:
QUERY_DOCUMENT_KEYS = {
    "name": (),
    "document": ("definitions",),
    "operation_definition": (
        "name",
        "variable_definitions",
        "directives",
        "selection_set",
    ),
    "variable_definition": ("variable", "type", "default_value", "directives"),
    "variable": ("name",),
    "selection_set": ("selections",),
    "field": ("alias", "name", "arguments", "directives", "selection_set"),
    "argument": ("name", "value"),
    "fragment_spread": ("name", "directives"),
    "inline_fragment": ("type_condition", "directives", "selection_set"),
    "fragment_definition": (
        # Note: fragment variable definitions are experimental and may be changed or
        # removed in the future.
        "name",
        "variable_definitions",
        "type_condition",
        "directives",
        "selection_set",
    ),
    "int_value": (),
    "float_value": (),
    "string_value": (),
    "boolean_value": (),
    "enum_value": (),
    "list_value": ("values",),
    "object_value": ("fields",),
    "object_field": ("name", "value"),
    "directive": ("name", "arguments"),
    "named_type": ("name",),
    "list_type": ("type",),
    "non_null_type": ("type",),
    "schema_definition": ("directives", "operation_types"),
    "operation_type_definition": ("type",),
    "scalar_type_definition": ("description", "name", "directives"),
    "object_type_definition": (
        "description",
        "name",
        "interfaces",
        "directives",
        "fields",
    ),
    "field_definition": ("description", "name", "arguments", "type", "directives"),
    "input_value_definition": (
        "description",
        "name",
        "type",
        "default_value",
        "directives",
    ),
    "interface_type_definition": ("description", "name", "directives", "fields"),
    "union_type_definition": ("description", "name", "directives", "types"),
    "enum_type_definition": ("description", "name", "directives", "values"),
    "enum_value_definition": ("description", "name", "directives"),
    "input_object_type_definition": ("description", "name", "directives", "fields"),
    "directive_definition": ("description", "name", "arguments", "locations"),
    "schema_extension": ("directives", "operation_types"),
    "scalar_type_extension": ("name", "directives"),
    "object_type_extension": ("name", "interfaces", "directives", "fields"),
    "interface_type_extension": ("name", "directives", "fields"),
    "union_type_extension": ("name", "directives", "types"),
    "enum_type_extension": ("name", "directives", "values"),
    "input_object_type_extension": ("name", "directives", "fields"),
}


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

        def enter(self, node, key, parent, path, ancestors):
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
        of this node. These correspond to array indices in `path`.
        Note: ancestors includes arrays which contain the parent of visited node.

    You can also define node kind specific methods by suffixing them with an underscore
    followed by the kind of the node to be visited. For instance, to visit `field`
    nodes, you would defined the methods `enter_field()` and/or `leave_field()`, with
    the same signature as above. If no kind specific method has been defined for a given
    node, the generic method is called.
    """

    # Provide special return values as attributes
    BREAK, SKIP, REMOVE, IDLE = BREAK, SKIP, REMOVE, IDLE

    def __init_subclass__(cls, **kwargs):
        """Verify that all defined handlers are valid."""
        super().__init_subclass__(**kwargs)
        for attr, val in cls.__dict__.items():
            if attr.startswith("_"):
                continue
            attr = attr.split("_", 1)
            attr, kind = attr if len(attr) > 1 else (attr[0], None)
            if attr in ("enter", "leave"):
                if kind:
                    name = snake_to_camel(kind) + "Node"
                    try:
                        node_cls = getattr(ast, name)
                        if not issubclass(node_cls, Node):
                            raise AttributeError
                    except AttributeError:
                        raise AttributeError(f"Invalid AST node kind: {kind}")

    @classmethod
    def get_visit_fn(cls, kind, is_leaving=False) -> Callable:
        """Get the visit function for the given node kind and direction."""
        method = "leave" if is_leaving else "enter"
        visit_fn = getattr(cls, f"{method}_{kind}", None)
        if not visit_fn:
            visit_fn = getattr(cls, method, None)
        return visit_fn


class Stack(NamedTuple):
    """A stack for the visit function."""

    in_array: bool
    idx: int
    keys: Tuple[Node, ...]
    edits: List[Tuple[Union[int, str], Node]]
    prev: Any  # 'Stack' (python/mypy/issues/731)


def visit(root: Node, visitor: Visitor, visitor_keys=None) -> Any:
    """Visit each node in an AST.

    `visit()` will walk through an AST using a depth first traversal, calling the
    visitor's enter methods at each node in the traversal, and calling the leave methods
    after visiting that node and all of its child nodes.

    By returning different values from the enter and leave methods, the behavior of the
    visitor can be altered, including skipping over a sub-tree of the AST (by returning
    False), editing the AST by returning a value or None to remove the value, or to stop
    the whole traversal by returning `BREAK`.

    When using `visit()` to edit an AST, the original AST will not be modified, and a
    new version of the AST with the changes applied will be returned from the visit
    function.

    To customize the node attributes to be used for traversal, you can provide a
    dictionary visitor_keys mapping node kinds to node attributes.
    """
    if not isinstance(root, Node):
        raise TypeError(f"Not an AST Node: {inspect(root)}")
    if not isinstance(visitor, Visitor):
        raise TypeError(f"Not an AST Visitor class: {inspect(visitor)}")
    if visitor_keys is None:
        visitor_keys = QUERY_DOCUMENT_KEYS
    stack: Any = None
    in_array = isinstance(root, list)
    keys: Tuple[Node, ...] = (root,)
    idx = -1
    edits: List[Any] = []
    parent: Any = None
    path: List[Any] = []
    path_append = path.append
    path_pop = path.pop
    ancestors: List[Any] = []
    ancestors_append = ancestors.append
    ancestors_pop = ancestors.pop
    new_root = root

    while True:
        idx += 1
        is_leaving = idx == len(keys)
        is_edited = is_leaving and edits
        if is_leaving:
            key = path[-1] if ancestors else None
            node: Any = parent
            parent = ancestors_pop() if ancestors else None
            if is_edited:
                if in_array:
                    node = node[:]
                else:
                    node = copy(node)
            edit_offset = 0
            for edit_key, edit_value in edits:
                if in_array:
                    edit_key -= edit_offset
                if in_array and edit_value is REMOVE:
                    node.pop(edit_key)
                    edit_offset += 1
                else:
                    if isinstance(node, list):
                        node[edit_key] = edit_value
                    else:
                        setattr(node, edit_key, edit_value)

            idx = stack.idx
            keys = stack.keys
            edits = stack.edits
            in_array = stack.in_array
            stack = stack.prev
        else:
            if parent:
                if in_array:
                    key = idx
                    node = parent[key]
                else:
                    key = keys[idx]
                    node = getattr(parent, key, None)
            else:
                key = None
                node = new_root
            if node is None or node is REMOVE:
                continue
            if parent:
                path_append(key)

        if isinstance(node, list):
            result = None
        else:
            if not isinstance(node, Node):
                raise TypeError(f"Not an AST Node: {inspect(node)}")
            visit_fn = visitor.get_visit_fn(node.kind, is_leaving)
            if visit_fn:
                result = visit_fn(visitor, node, key, parent, path, ancestors)

                if result is BREAK:
                    break

                if result is SKIP:
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
            in_array = isinstance(node, list)
            keys = node if in_array else visitor_keys.get(node.kind, ())
            idx = -1
            edits = []
            if parent:
                ancestors_append(parent)
            parent = node

        if not stack:
            break

    if edits:
        new_root = edits[-1][1]

    return new_root


class ParallelVisitor(Visitor):
    """A Visitor which delegates to many visitors to run in parallel.

    Each visitor will be visited for each node before moving on.

    If a prior visitor edits a node, no following visitors will see that node.
    """

    def __init__(self, visitors: Sequence[Visitor]) -> None:
        """Create a new visitor from the given list of parallel visitors."""
        self.visitors = visitors
        self.skipping: List[Any] = [None] * len(visitors)

    def enter(self, node, *args):
        skipping = self.skipping
        for i, visitor in enumerate(self.visitors):
            if not skipping[i]:
                fn = visitor.get_visit_fn(node.kind)
                if fn:
                    result = fn(visitor, node, *args)
                    if result is SKIP:
                        skipping[i] = node
                    elif result == BREAK:
                        skipping[i] = BREAK
                    elif result is not None:
                        return result

    def leave(self, node, *args):
        skipping = self.skipping
        for i, visitor in enumerate(self.visitors):
            if not skipping[i]:
                fn = visitor.get_visit_fn(node.kind, is_leaving=True)
                if fn:
                    result = fn(visitor, node, *args)
                    if result == BREAK:
                        skipping[i] = BREAK
                    elif result is not None and result is not SKIP:
                        return result
            elif skipping[i] is node:
                skipping[i] = None


class TypeInfoVisitor(Visitor):
    """A visitor which maintains a provided TypeInfo."""

    def __init__(self, type_info: "TypeInfo", visitor: Visitor) -> None:
        self.type_info = type_info
        self.visitor = visitor

    def enter(self, node, *args):
        self.type_info.enter(node)
        fn = self.visitor.get_visit_fn(node.kind)
        if fn:
            result = fn(self.visitor, node, *args)
            if result is not None:
                self.type_info.leave(node)
                if isinstance(result, ast.Node):
                    self.type_info.enter(result)
            return result

    def leave(self, node, *args):
        fn = self.visitor.get_visit_fn(node.kind, is_leaving=True)
        result = fn(self.visitor, node, *args) if fn else None
        self.type_info.leave(node)
        return result
