from typing import Any, Set

from ...error import GraphQLError
from ...language import OperationDefinitionNode, VariableDefinitionNode
from . import ValidationContext, ValidationRule

__all__ = ["NoUndefinedVariablesRule"]


class NoUndefinedVariablesRule(ValidationRule):
    """No undefined variables

    A GraphQL operation is only valid if all variables encountered, both directly and
    via fragment spreads, are defined by that operation.

    See https://spec.graphql.org/draft/#sec-All-Variable-Uses-Defined

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import NoUndefinedVariablesRule
    >>> schema = build_schema('type Query { field(arg: ID): String }')
    >>> document = parse('query ($id: ID) { field(arg: $missing) }')
    >>> errors = validate(schema, document, [NoUndefinedVariablesRule])
    >>> print(errors[0].message)
    Variable '$missing' is not defined.
    >>> document = parse('query ($id: ID) { field(arg: $id) }')
    >>> validate(schema, document, [NoUndefinedVariablesRule])
    []
    """

    def __init__(self, context: ValidationContext):
        super().__init__(context)
        self.defined_variable_names: Set[str] = set()

    def enter_operation_definition(self, *_args: Any) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        self.defined_variable_names.clear()

    def leave_operation_definition(
        self, operation: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when leaving an operation definition node.

        :meta private:
        """
        usages = self.context.get_recursive_variable_usages(operation)
        defined_variables = self.defined_variable_names
        for usage in usages:
            node = usage.node
            var_name = node.name.value
            if var_name not in defined_variables:
                self.report_error(
                    GraphQLError(
                        (
                            f"Variable '${var_name}' is not defined"
                            f" by operation '{operation.name.value}'."
                            if operation.name
                            else f"Variable '${var_name}' is not defined."
                        ),
                        [node, operation],
                    )
                )

    def enter_variable_definition(
        self, node: VariableDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering a variable definition node.

        :meta private:
        """
        self.defined_variable_names.add(node.variable.name.value)
