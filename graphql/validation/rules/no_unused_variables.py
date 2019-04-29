from typing import List, Set

from ...error import GraphQLError
from ...language import OperationDefinitionNode, VariableDefinitionNode
from . import ValidationContext, ValidationRule

__all__ = ["NoUnusedVariablesRule", "unused_variable_message"]


def unused_variable_message(var_name: str, op_name: str = None) -> str:
    return (
        f"Variable '${var_name}' is never used in operation '{op_name}'."
        if op_name
        else f"Variable '${var_name}' is never used."
    )


class NoUnusedVariablesRule(ValidationRule):
    """No unused variables

    A GraphQL operation is only valid if all variables defined by an operation are used,
    either directly or within a spread fragment.
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self.variable_defs: List[VariableDefinitionNode] = []

    def enter_operation_definition(self, *_args):
        self.variable_defs.clear()

    def leave_operation_definition(self, operation: OperationDefinitionNode, *_args):
        variable_name_used: Set[str] = set()
        usages = self.context.get_recursive_variable_usages(operation)
        op_name = operation.name.value if operation.name else None

        for usage in usages:
            variable_name_used.add(usage.node.name.value)

        for variable_def in self.variable_defs:
            variable_name = variable_def.variable.name.value
            if variable_name not in variable_name_used:
                self.report_error(
                    GraphQLError(
                        unused_variable_message(variable_name, op_name), variable_def
                    )
                )

    def enter_variable_definition(self, definition: VariableDefinitionNode, *_args):
        self.variable_defs.append(definition)
