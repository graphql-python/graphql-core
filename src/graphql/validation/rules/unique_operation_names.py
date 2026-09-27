"""Unique operation names rule"""

from typing import Any, Dict

from ...error import GraphQLError
from ...language import NameNode, OperationDefinitionNode, VisitorAction, SKIP
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueOperationNamesRule"]


class UniqueOperationNamesRule(ASTValidationRule):
    """Unique operation names

    A GraphQL document is only valid if all defined operations have unique names.

    See https://spec.graphql.org/draft/#sec-Operation-Name-Uniqueness

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import UniqueOperationNamesRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('query Same { name } query Same { name }')
    >>> errors = validate(schema, document, [UniqueOperationNamesRule])
    >>> print(errors[0].message)
    There can be only one operation named 'Same'.
    >>> document = parse('query One { name } query Two { name }')
    >>> validate(schema, document, [UniqueOperationNamesRule])
    []
    """

    def __init__(self, context: ASTValidationContext):
        super().__init__(context)
        self.known_operation_names: Dict[str, NameNode] = {}

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> VisitorAction:
        """Called when entering an operation definition node.

        :meta private:
        """
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
        return SKIP

    @staticmethod
    def enter_fragment_definition(*_args: Any) -> VisitorAction:
        return SKIP
