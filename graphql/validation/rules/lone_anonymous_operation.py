from ...language import OperationDefinitionNode
from ...error import GraphQLError
from . import ValidationRule

__all__ = [
    'LoneAnonymousOperationRule', 'anonymous_operation_not_alone_message']


def anonymous_operation_not_alone_message() -> str:
    return 'This anonymous operation must be the only defined operation.'


class LoneAnonymousOperationRule(ValidationRule):
    """Lone anonymous operation

    A GraphQL document is only valid if when it contains an anonymous operation
    (the query short-hand) that it contains only that one operation definition.

    """

    def __init__(self, context):
        super().__init__(context)
        self.operation_count = 0

    def enter_document(self, node, *_args):
        self.operation_count = sum(
            1 for definition in node.definitions
            if isinstance(definition, OperationDefinitionNode))

    def enter_operation_definition(self, node, *_args):
        if not node.name and self.operation_count > 1:
            self.report_error(GraphQLError(
                anonymous_operation_not_alone_message(), [node]))
