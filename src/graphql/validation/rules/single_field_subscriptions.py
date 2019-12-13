from ...error import GraphQLError
from ...language import OperationDefinitionNode, OperationType
from . import ASTValidationRule

__all__ = ["SingleFieldSubscriptionsRule"]


class SingleFieldSubscriptionsRule(ASTValidationRule):
    """Subscriptions must only include one field.

    A GraphQL subscription is valid only if it contains a single root.
    """

    def enter_operation_definition(self, node: OperationDefinitionNode, *_args):
        if node.operation == OperationType.SUBSCRIPTION:
            if len(node.selection_set.selections) != 1:
                self.report_error(
                    GraphQLError(
                        (
                            f"Subscription '{node.name.value}'"
                            if node.name
                            else "Anonymous Subscription"
                        )
                        + " must select only one top level field.",
                        node.selection_set.selections[1:],
                    )
                )
