"""Known operation types rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from . import ValidationRule

if TYPE_CHECKING:
    from ...language import OperationDefinitionNode

__all__ = ["KnownOperationTypesRule"]


class KnownOperationTypesRule(ValidationRule):
    """Known Operation Types

    A GraphQL document is only valid if when it contains an operation,
    the root type for the operation exists within the schema.

    See https://spec.graphql.org/draft/#sec-Operation-Type-Existence

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import KnownOperationTypesRule
    >>> schema = build_schema('type Query { greeting: String }')
    >>> document = parse('mutation { greeting }')
    >>> errors = validate(schema, document, [KnownOperationTypesRule])
    >>> print(errors[0].message)
    The mutation operation is not supported by the schema.
    >>> document = parse('{ greeting }')
    >>> validate(schema, document, [KnownOperationTypesRule])
    []
    """

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        operation = node.operation
        if not self.context.schema.get_root_type(operation):
            self.report_error(
                GraphQLError(
                    f"The {operation.value} operation is not supported by the schema.",
                    node,
                )
            )
