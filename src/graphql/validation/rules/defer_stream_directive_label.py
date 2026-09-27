"""Defer stream directive label rule"""

from typing import Any

from ...error import GraphQLError
from ...language import DirectiveNode, Node, NullValueNode, StringValueNode
from ...type import GraphQLDeferDirective, GraphQLStreamDirective
from . import ASTValidationRule, ValidationContext

__all__ = ["DeferStreamDirectiveLabel"]


class DeferStreamDirectiveLabel(ASTValidationRule):
    """Defer and stream directive labels are unique

    A GraphQL document is only valid if defer and stream directives' label argument
    is static and unique.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import DeferStreamDirectiveLabel
    >>> schema = build_schema('type Query { friends: [String] }')
    >>> document = parse(
    ...     '{ friends @stream(label: "friends")'
    ...     ' other: friends @stream(label: "friends") }'
    ... )
    >>> errors = validate(schema, document, [DeferStreamDirectiveLabel])
    >>> print(errors[0].message)
    Defer/Stream directive label argument must be unique.
    >>> document = parse(
    ...     '{ friends @stream(label: "friends")'
    ...     ' other: friends @stream(label: "otherFriends") }'
    ... )
    >>> validate(schema, document, [DeferStreamDirectiveLabel])
    []
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self.known_labels: dict[str, Node] = {}

    def enter_directive(
        self,
        node: DirectiveNode,
        _key: Any,
        _parent: Any,
        _path: Any,
        _ancestors: list[Node],
    ) -> None:
        """Called when entering a directive node.

        :meta private:
        """
        if node.name.value not in (
            GraphQLDeferDirective.name,
            GraphQLStreamDirective.name,
        ):
            return
        try:
            label_argument = next(
                arg for arg in node.arguments or () if arg.name.value == "label"
            )
        except StopIteration:
            return
        label_value = label_argument.value
        if isinstance(label_value, NullValueNode):
            return
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
