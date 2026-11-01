"""Max introspection depth rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from ...language import SKIP, FieldNode, FragmentSpreadNode, Node, VisitorAction
from . import ASTValidationRule, ValidationContext

if TYPE_CHECKING:
    from collections.abc import Iterator

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
        self._checked_fragments: dict[str, int] = {}

    def _check_depth(
        self, node: Node, visited_fragments: dict[str, int], depth: int = 0
    ) -> bool:
        """Check whether the maximum introspection depth has been reached.

        Counts the depth of list fields in "__Type" recursively
        and returns `True` if the limit has been reached.
        """
        # Walk depth-first with an explicit stack in the same order as a recursive
        # walk, so that long fragment chains cannot exceed the recursion limit.
        stack: list[tuple[Iterator[Node], int]] = [(iter((node,)), depth)]
        while stack:
            nodes, depth = stack[-1]
            next_node = next(nodes, None)
            if next_node is None:
                stack.pop()
                continue
            node = next_node
            if isinstance(node, FragmentSpreadNode):
                fragment_name = node.name.value
                # Skip fragments already checked at this depth or deeper.
                # This also stops fragment cycles that do not increase the depth.
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
                stack.append((iter(fragment.selection_set.selections), depth))
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
                    return True

            # handle fields and inline fragments
            try:
                selection_set = node.selection_set  # type: ignore[attr-defined]
            except AttributeError:  # pragma: no cover
                selection_set = None
            if selection_set:
                stack.append((iter(selection_set.selections), depth))

        return False

    def enter_field(self, node: FieldNode, *_args: Any) -> VisitorAction:
        """Called when entering a field node.

        :meta private:
        """
        if node.name.value in ("__schema", "__type"):
            visited_fragments: dict[str, int] = {}
            if self._check_depth(node, visited_fragments):
                self.report_error(
                    GraphQLError(
                        "Maximum introspection depth exceeded",
                        [node],
                    )
                )
                return SKIP
            self._checked_fragments.update(visited_fragments)
        return None
