from typing import Dict

from ...error import GraphQLError
from ...language import NameNode, OperationDefinitionNode
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueOperationNamesRule"]


class UniqueOperationNamesRule(ASTValidationRule):
    """Unique operation names

    A GraphQL document is only valid if all defined operations have unique names.
    """

    def __init__(self, context: ASTValidationContext):
        super().__init__(context)
        self.known_operation_names: Dict[str, NameNode] = {}

    def enter_operation_definition(self, node: OperationDefinitionNode, *_args):
        operation_name = node.name
        if operation_name:
            known_operation_names = self.known_operation_names
            if operation_name.value in known_operation_names:
                self.report_error(
                    GraphQLError(
                        "There can be only one operation"
                        f" named '{operation_name.value}'.",
                        [known_operation_names[operation_name.value], operation_name],
                    )
                )
            else:
                known_operation_names[operation_name.value] = operation_name
        return self.SKIP

    def enter_fragment_definition(self, *_args):
        return self.SKIP
