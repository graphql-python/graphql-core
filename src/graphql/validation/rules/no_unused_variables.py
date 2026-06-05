"""No unused variables rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from . import ValidationRule

if TYPE_CHECKING:
    from ...language import FragmentDefinitionNode, OperationDefinitionNode

__all__ = ["NoUnusedVariablesRule"]


class NoUnusedVariablesRule(ValidationRule):
    """No unused variables

    A GraphQL operation is only valid if all variables defined by an operation are used,
    either directly or within a spread fragment.

    See https://spec.graphql.org/draft/#sec-All-Variables-Used
    """

    def leave_fragment_definition(
        self, fragment: FragmentDefinitionNode, *_args: Any
    ) -> None:
        usages = self.context.get_variable_usages(fragment)
        argument_name_used = {usage.node.name.value for usage in usages}
        for var_def in fragment.variable_definitions:
            arg_name = var_def.variable.name.value
            if arg_name not in argument_name_used:
                self.report_error(
                    GraphQLError(
                        f"Variable '${arg_name}' is never used"
                        f" in fragment '{fragment.name.value}'.",
                        var_def,
                    )
                )

    def leave_operation_definition(
        self, operation: OperationDefinitionNode, *_args: Any
    ) -> None:
        operation_variable_name_used: set[str] = set()
        usages = self.context.get_recursive_variable_usages(operation)

        for usage in usages:
            if not usage.fragment_variable_definition:
                operation_variable_name_used.add(usage.node.name.value)

        for variable_def in operation.variable_definitions:
            variable_name = variable_def.variable.name.value
            if variable_name not in operation_variable_name_used:
                self.report_error(
                    GraphQLError(
                        f"Variable '${variable_name}' is never used"
                        f" in operation '{operation.name.value}'."
                        if operation.name
                        else f"Variable '${variable_name}' is never used.",
                        variable_def,
                    )
                )
