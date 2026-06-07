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
    """

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        operation = node.operation
        if not self.context.schema.get_root_type(operation):
            self.report_error(
                GraphQLError(
                    f"The {operation.value} operation is not supported by the schema.",
                    node,
                )
            )
