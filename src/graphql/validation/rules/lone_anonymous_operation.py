"""Lone anonymous operation rule"""

from typing import Any

from ...error import GraphQLError
from ...language import DocumentNode, OperationDefinitionNode
from . import ASTValidationContext, ASTValidationRule

__all__ = ["LoneAnonymousOperationRule"]


class LoneAnonymousOperationRule(ASTValidationRule):
    """Lone anonymous operation

    A GraphQL document is only valid if when it contains an anonymous operation
    (the query short-hand) that it contains only that one operation definition.

    See https://spec.graphql.org/draft/#sec-Lone-Anonymous-Operation

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import LoneAnonymousOperationRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('query { name } query Other { name }')
    >>> errors = validate(schema, document, [LoneAnonymousOperationRule])
    >>> print(errors[0].message)
    This anonymous operation must be the only defined operation.
    >>> document = parse('{ name }')
    >>> validate(schema, document, [LoneAnonymousOperationRule])
    []
    """

    def __init__(self, context: ASTValidationContext):
        super().__init__(context)
        self.operation_count = 0

    def enter_document(self, node: DocumentNode, *_args: Any) -> None:
        """Called when entering a document node.

        :meta private:
        """
        self.operation_count = sum(
            isinstance(definition, OperationDefinitionNode)
            for definition in node.definitions
        )

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        if not node.name and self.operation_count > 1:
            self.report_error(
                GraphQLError(
                    "This anonymous operation must be the only defined operation.", node
                )
            )
