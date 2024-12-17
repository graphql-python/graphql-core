"""Defer stream directive on valid operations rule"""

from __future__ import annotations

from typing import Any

from ...error import GraphQLError
from ...language import (
    BooleanValueNode,
    DirectiveNode,
    FragmentDefinitionNode,
    Node,
    OperationDefinitionNode,
    OperationType,
    VariableNode,
)
from ...type import GraphQLDeferDirective, GraphQLStreamDirective
from . import ASTValidationRule, ValidationContext

__all__ = ["DeferStreamDirectiveOnValidOperationsRule"]


def if_argument_can_be_false(node: DirectiveNode) -> bool:
    for argument in node.arguments:
        if argument.name.value == "if":
            if isinstance(argument.value, BooleanValueNode):
                if argument.value.value:
                    return False
            elif not isinstance(argument.value, VariableNode):
                return False
            return True
    return False


class DeferStreamDirectiveOnValidOperationsRule(ASTValidationRule):
    """Defer and stream directives are used on valid root field

    A GraphQL document is only valid if defer directives are not used on root
    mutation or subscription types.
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self.fragments_used_on_subscriptions: set[str] = set()

    def enter_operation_definition(
        self, operation: OperationDefinitionNode, *_args: Any
    ) -> None:
        if operation.operation == OperationType.SUBSCRIPTION:
            fragments = self.context.get_recursively_referenced_fragments(operation)
            for fragment in fragments:
                self.fragments_used_on_subscriptions.add(fragment.name.value)

    def enter_directive(
        self,
        node: DirectiveNode,
        _key: Any,
        _parent: Any,
        _path: Any,
        ancestors: list[Node],
    ) -> None:
        try:
            definition_node = ancestors[2]
        except IndexError:  # pragma: no cover
            return
        if (
            isinstance(definition_node, FragmentDefinitionNode)
            and definition_node.name.value in self.fragments_used_on_subscriptions
        ) or (
            isinstance(definition_node, OperationDefinitionNode)
            and definition_node.operation == OperationType.SUBSCRIPTION
        ):
            if node.name.value == GraphQLDeferDirective.name:
                if not if_argument_can_be_false(node):
                    msg = (
                        "Defer directive not supported on subscription operations."
                        " Disable `@defer` by setting the `if` argument to `false`."
                    )
                    self.report_error(GraphQLError(msg, node))
            elif node.name.value == GraphQLStreamDirective.name:  # noqa: SIM102
                if not if_argument_can_be_false(node):
                    msg = (
                        "Stream directive not supported on subscription operations."
                        " Disable `@stream` by setting the `if` argument to `false`."
                    )
                    self.report_error(GraphQLError(msg, node))
