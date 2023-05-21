from typing import Any, Dict, List

from ...error import GraphQLError
from ...language import DirectiveNode, Node, StringValueNode
from ...type import GraphQLDeferDirective, GraphQLStreamDirective
from . import ASTValidationRule, ValidationContext


__all__ = ["DeferStreamDirectiveLabel"]


class DeferStreamDirectiveLabel(ASTValidationRule):
    """Defer and stream directive labels are unique

    A GraphQL document is only valid if defer and stream directives' label argument
    is static and unique.
    """

    def __init__(self, context: ValidationContext):
        super().__init__(context)
        self.known_labels: Dict[str, Node] = {}

    def enter_directive(
        self,
        node: DirectiveNode,
        _key: Any,
        _parent: Any,
        _path: Any,
        _ancestors: List[Node],
    ) -> None:
        if node.name.value not in (
            GraphQLDeferDirective.name,
            GraphQLStreamDirective.name,
        ):
            return
        try:
            label_argument = next(
                arg for arg in node.arguments if arg.name.value == "label"
            )
        except StopIteration:
            return
        label_value = label_argument.value
        if not isinstance(label_value, StringValueNode):
            self.report_error(
                GraphQLError(
                    f"{node.name.value.capitalize()} directive label argument"
                    " must be a static string.",
                    node,
                ),
            )
            return
        label_name = label_value.value
        known_labels = self.known_labels
        if label_name in known_labels:
            self.report_error(
                GraphQLError(
                    "Defer/Stream directive label argument must be unique.",
                    [known_labels[label_name], node],
                ),
            )
            return
        known_labels[label_name] = node
