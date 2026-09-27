"""No unused variables rule"""

from typing import Any, List, Set

from ...error import GraphQLError
from ...language import OperationDefinitionNode, VariableDefinitionNode
from . import ValidationContext, ValidationRule

__all__ = ["NoUnusedVariablesRule"]


class NoUnusedVariablesRule(ValidationRule):
    """No unused variables

    A GraphQL operation is only valid if all variables defined by an operation are used,
    either directly or within a spread fragment.

    See https://spec.graphql.org/draft/#sec-All-Variables-Used

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import NoUnusedVariablesRule
    >>> schema = build_schema('type Query { field(arg: ID): String name: String }')
    >>> document = parse('query ($id: ID) { name }')
    >>> errors = validate(schema, document, [NoUnusedVariablesRule])
    >>> print(errors[0].message)
    Variable '$id' is never used.
    >>> document = parse('query ($id: ID) { field(arg: $id) }')
    >>> validate(schema, document, [NoUnusedVariablesRule])
    []
    """

    def __init__(self, context: ValidationContext):
        super().__init__(context)
        self.variable_defs: List[VariableDefinitionNode] = []

    def enter_operation_definition(self, *_args: Any) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        self.variable_defs.clear()

    def leave_operation_definition(
        self, operation: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when leaving an operation definition node.

        :meta private:
        """
        variable_name_used: Set[str] = set()
        usages = self.context.get_recursive_variable_usages(operation)

        for usage in usages:
            variable_name_used.add(usage.node.name.value)

        for variable_def in self.variable_defs:
            variable_name = variable_def.variable.name.value
            if variable_name not in variable_name_used:
                self.report_error(
                    GraphQLError(
                        (
                            f"Variable '${variable_name}' is never used"
                            f" in operation '{operation.name.value}'."
                            if operation.name
                            else f"Variable '${variable_name}' is never used."
                        ),
                        variable_def,
                    )
                )

    def enter_variable_definition(
        self, definition: VariableDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering a variable definition node.

        :meta private:
        """
        self.variable_defs.append(definition)
