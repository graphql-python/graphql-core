"""Unique variable names rule"""

from operator import attrgetter
from typing import Any

from ...error import GraphQLError
from ...language import OperationDefinitionNode
from ...pyutils import group_by
from . import ASTValidationRule

__all__ = ["UniqueVariableNamesRule"]


class UniqueVariableNamesRule(ASTValidationRule):
    """Unique variable names

    A GraphQL operation is only valid if all its variables are uniquely named.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import UniqueVariableNamesRule
    >>> schema = build_schema('type Query { field(arg: ID): String }')
    >>> document = parse('query ($id: ID, $id: ID) { field(arg: $id) }')
    >>> errors = validate(schema, document, [UniqueVariableNamesRule])
    >>> print(errors[0].message)
    There can be only one variable named '$id'.
    >>> document = parse('query ($id: ID) { field(arg: $id) }')
    >>> validate(schema, document, [UniqueVariableNamesRule])
    []
    """

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        variable_definitions = node.variable_definitions

        seen_variable_definitions = group_by(
            variable_definitions, attrgetter("variable.name.value")
        )

        for variable_name, variable_nodes in seen_variable_definitions.items():
            if len(variable_nodes) > 1:
                self.report_error(
                    GraphQLError(
                        f"There can be only one variable named '${variable_name}'.",
                        [node.variable.name for node in variable_nodes],
                    )
                )
