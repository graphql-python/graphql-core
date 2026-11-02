"""No undefined variables rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from . import ValidationRule

if TYPE_CHECKING:
    from ...language import OperationDefinitionNode

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

    def enter_operation_definition(
        self, operation: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        variable_name_defined = {
            node.variable.name.value for node in operation.variable_definitions or ()
        }
        usages = self.context.get_recursive_variable_usages(operation)
        for usage in usages:
            if usage.fragment_variable_definition:
                continue
            node = usage.node
            var_name = node.name.value
            if var_name not in variable_name_defined:
                self.report_error(
                    GraphQLError(
                        f"Variable '${var_name}' is not defined"
                        f" by operation '{operation.name.value}'."
                        if operation.name
                        else f"Variable '${var_name}' is not defined.",
                        [node, operation],
                    )
                )
