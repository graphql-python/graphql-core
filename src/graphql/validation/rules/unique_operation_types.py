"""Unique operation types rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from ...language import (
    SKIP,
    OperationType,
    OperationTypeDefinitionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    VisitorAction,
)

if TYPE_CHECKING:
    from ...type import GraphQLObjectType
from . import SDLValidationContext, SDLValidationRule

__all__ = ["UniqueOperationTypesRule"]


class UniqueOperationTypesRule(SDLValidationRule):
    """Unique operation types

    A GraphQL document is only valid if it has only one type per operation.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema
    >>> from graphql.validation import UniqueOperationTypesRule
    >>> from graphql.validation.specified_rules import specified_sdl_rules
    >>> UniqueOperationTypesRule in specified_sdl_rules
    True
    >>> sdl = (
    ...     'schema { query: Query query: Other } type Query { name: String }'
    ...     ' type Other { name: String }'
    ... )
    >>> build_schema(sdl)
    Traceback (most recent call last):
    ...
    TypeError: There can be only one query type in schema.
    >>> sdl = 'schema { query: Query } type Query { name: String }'
    >>> schema = build_schema(sdl)
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        schema = context.schema
        self.defined_operation_types: dict[
            OperationType, OperationTypeDefinitionNode
        ] = {}
        self.existing_operation_types: dict[OperationType, GraphQLObjectType | None] = (
            {
                OperationType.QUERY: schema.query_type,
                OperationType.MUTATION: schema.mutation_type,
                OperationType.SUBSCRIPTION: schema.subscription_type,
            }
            if schema
            else {}
        )
        self.schema = schema

    def check_operation_types(
        self, node: SchemaDefinitionNode | SchemaExtensionNode, *_args: Any
    ) -> VisitorAction:
        """Report root operation types that are defined more than once.

        :meta private:
        """
        for operation_type in node.operation_types or []:
            operation = operation_type.operation
            already_defined_operation_type = self.defined_operation_types.get(operation)

            if self.existing_operation_types.get(operation):
                self.report_error(
                    GraphQLError(
                        f"Type for {operation.value} already defined in the schema."
                        " It cannot be redefined.",
                        operation_type,
                    )
                )
            elif already_defined_operation_type:
                self.report_error(
                    GraphQLError(
                        f"There can be only one {operation.value} type in schema.",
                        [already_defined_operation_type, operation_type],
                    )
                )
            else:
                self.defined_operation_types[operation] = operation_type
        return SKIP

    enter_schema_definition = enter_schema_extension = check_operation_types
