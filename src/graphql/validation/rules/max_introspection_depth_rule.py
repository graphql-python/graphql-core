"""Max introspection depth rule"""

from typing import Any, Dict, Iterator, List, Optional, Tuple

from ...error import GraphQLError
from ...language import SKIP, FieldNode, FragmentSpreadNode, Node, VisitorAction
from . import ASTValidationRule, ValidationContext

__all__ = ["MaxIntrospectionDepthRule"]

MAX_LIST_DEPTH = 3


class MaxIntrospectionDepthRule(ASTValidationRule):
    """Checks maximum introspection depth

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import MaxIntrospectionDepthRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse(
    ...     '{ __schema { types { fields { type { fields {'
    ...     ' type { fields { name } } } } } } } }'
    ... )
    >>> errors = validate(schema, document, [MaxIntrospectionDepthRule])
    >>> print(errors[0].message)
    Maximum introspection depth exceeded
    >>> document = parse('{ __schema { queryType { name } } }')
    >>> validate(schema, document, [MaxIntrospectionDepthRule])
    []
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self._get_fragment = context.get_fragment
        # For each fragment, the greatest entry depth at which its check completed
        # without reaching the limit. Shared across root checks.
        # Entry depth is the list depth before entering the fragment.
        self._checked_fragments: Dict[str, int] = {}
        # For each fragment, the smallest entry depth at which its check reached
        # the limit. Shared across root checks.
        self._exceeded_fragments: Dict[str, int] = {}

    def _check_depth(
        self, node: Node, visited_fragments: Dict[str, int], depth: int = 0
    ) -> bool:
        """Check whether the maximum introspection depth has been reached.

        Counts the depth of list fields in "__Type" recursively
        and returns ``True`` if the limit has been reached.
        """
        # Walk depth-first with an explicit stack in the same order as a recursive
        # walk, so that long fragment chains cannot exceed the recursion limit.
        # The entries for the selections of a fragment also carry the fragment name,
        # and their depth is the entry depth of that fragment.
        stack: List[Tuple[Iterator[Node], int, Optional[str]]] = [
            (iter((node,)), depth, None)
        ]
        while stack:
            nodes, depth, entered_fragment = stack[-1]
            next_node = next(nodes, None)
            if next_node is None:
                stack.pop()
                if entered_fragment is not None:
                    self._checked_fragments[entered_fragment] = depth
                continue
            node = next_node
            if isinstance(node, FragmentSpreadNode):
                fragment_name = node.name.value
                exceeded_depth = self._exceeded_fragments.get(fragment_name)
                # A check that reached the limit will also do so when repeated at an
                # equal or greater entry depth.
                if exceeded_depth is not None and exceeded_depth <= depth:
                    self._mark_exceeded_fragments(stack)
                    return True
                # At equal or shallower entry depths, skip revisits to break cycles
                # or reuse a completed successful check.
                if (
                    visited_fragments.get(fragment_name, -1) >= depth
                    or self._checked_fragments.get(fragment_name, -1) >= depth
                ):
                    continue
                fragment = self._get_fragment(fragment_name)
                if not fragment:
                    # Missing fragments checks are handled by `KnownFragmentNamesRule`.
                    continue

                visited_fragments[fragment_name] = depth
                stack.append(
                    (iter(fragment.selection_set.selections), depth, fragment_name)
                )
                continue

            if isinstance(node, FieldNode) and node.name.value in (
                # check all introspection lists
                "fields",
                "interfaces",
                "possibleTypes",
                "inputFields",
            ):
                depth += 1
                if depth >= MAX_LIST_DEPTH:
                    self._mark_exceeded_fragments(stack)
                    return True

            # handle fields and inline fragments
            try:
                selection_set = node.selection_set  # type: ignore[attr-defined]
            except AttributeError:  # pragma: no cover
                selection_set = None
            if selection_set:
                stack.append((iter(selection_set.selections), depth, None))

        return False

    def _mark_exceeded_fragments(
        self, stack: List[Tuple[Iterator[Node], int, Optional[str]]]
    ) -> None:
        """Record that all fragments being checked have reached the limit.

        Goes from the innermost to the outermost fragment like the return of a
        recursive walk, so that a fragment entered twice keeps the smaller depth.
        """
        for _nodes, depth, entered_fragment in reversed(stack):
            if entered_fragment is not None:
                self._exceeded_fragments[entered_fragment] = depth

    def enter_field(self, node: FieldNode, *_args: Any) -> VisitorAction:
        """Called when entering a field node.

        :meta private:
        """
        if node.name.value in ("__schema", "__type"):
            # For each fragment, the greatest entry depth at which it was visited
            # during this root check, including visits still in progress.
            visited_fragments: Dict[str, int] = {}
            if self._check_depth(node, visited_fragments):
                self.report_error(
                    GraphQLError(
                        "Maximum introspection depth exceeded",
                        [node],
                    )
                )
                return SKIP
        return None
