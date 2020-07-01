from typing import Any, Dict

from ...error import GraphQLError
from ...language import NameNode, VariableDefinitionNode
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueVariableNamesRule"]


class UniqueVariableNamesRule(ASTValidationRule):
    """Unique variable names

    A GraphQL operation is only valid if all its variables are uniquely named.
    """

    def __init__(self, context: ASTValidationContext):
        super().__init__(context)
        self.known_variable_names: Dict[str, NameNode] = {}

    def enter_operation_definition(self, *_args: Any) -> None:
        self.known_variable_names.clear()

    def enter_variable_definition(
        self, node: VariableDefinitionNode, *_args: Any
    ) -> None:
        known_variable_names = self.known_variable_names
        variable_name = node.variable.name.value
        if variable_name in known_variable_names:
            self.report_error(
                GraphQLError(
                    f"There can be only one variable named '${variable_name}'.",
                    [known_variable_names[variable_name], node.variable.name],
                )
            )
        else:
            known_variable_names[variable_name] = node.variable.name
