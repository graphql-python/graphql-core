"""Max introspection depth rule"""

from typing import Dict, Any

from ...error import GraphQLError
from ...language import SKIP, FieldNode, FragmentSpreadNode, Node, VisitorAction
from . import ASTValidationRule, ValidationContext

__all__ = ["MaxIntrospectionDepthRule"]

MAX_LIST_DEPTH = 3


class MaxIntrospectionDepthRule(ASTValidationRule):
    """Checks maximum introspection depth"""

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self._visited_fragments: Dict[str, None] = {}
        self._get_fragment = context.get_fragment

    def _check_depth(self, node: Node, depth: int = 0) -> bool:
        """Check whether the maximum introspection depth has been reached.

        Counts the depth of list fields in "__Type" recursively
        and returns `True` if the limit has been reached.
        """
        if isinstance(node, FragmentSpreadNode):
            visited_fragments = self._visited_fragments
            fragment_name = node.name.value
            if fragment_name in visited_fragments:
                # Fragment cycles are handled by `NoFragmentCyclesRule`.
                return False
            fragment = self._get_fragment(fragment_name)
            if not fragment:
                # Missing fragments checks are handled by the `KnownFragmentNamesRule`.
                return False

            # Rather than following an immutable programming pattern which has
            # significant memory and garbage collection overhead, we've opted to take
            # a mutable approach for efficiency's sake. Importantly visiting a fragment
            # twice is fine, so long as you don't do one visit inside the other.
            visited_fragments[fragment_name] = None
            try:
                return self._check_depth(fragment, depth)
            finally:
                del visited_fragments[fragment_name]

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

        # hendle fields and inline fragments
        try:
            selection_set = node.selection_set  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover
            selection_set = None
        if selection_set:
            for child in selection_set.selections:
                if self._check_depth(child, depth):
                    return True

        return False

    def enter_field(self, node: FieldNode, *_args: Any) -> VisitorAction:
        if node.name.value in ("__schema", "__type") and self._check_depth(node):
            self.report_error(
                GraphQLError(
                    "Maximum introspection depth exceeded",
                    [node],
                )
            )
            return SKIP
        return None
