from typing import Dict, Optional, Union

from ...error import GraphQLError
from ...language import (
    OperationTypeDefinitionNode,
    OperationType,
    SchemaDefinitionNode,
    SchemaExtensionNode,
)
from ...type import GraphQLObjectType
from . import SDLValidationContext, SDLValidationRule

__all__ = [
    "UniqueOperationTypesRule",
    "duplicate_operation_type_message",
    "existed_operation_type_message",
]


def duplicate_operation_type_message(operation: str) -> str:
    return f"There can be only one '{operation}' type in schema."


def existed_operation_type_message(operation: str) -> str:
    return (
        f"Type for '{operation}' already defined in the schema."
        " It cannot be redefined."
    )


class UniqueOperationTypesRule(SDLValidationRule):
    """Unique operation types

    A GraphQL document is only valid if it has only one type per operation.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        schema = context.schema
        self.defined_operation_types: Dict[
            OperationType, OperationTypeDefinitionNode
        ] = {}
        self.existing_operation_types: Dict[
            OperationType, Optional[GraphQLObjectType]
        ] = (
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
        self, node: Union[SchemaDefinitionNode, SchemaExtensionNode], *_args
    ):
        for operation_type in node.operation_types or []:
            operation = operation_type.operation
            already_defined_operation_type = self.defined_operation_types.get(operation)

            if self.existing_operation_types.get(operation):
                self.report_error(
                    GraphQLError(
                        existed_operation_type_message(operation.value), operation_type
                    )
                )
            elif already_defined_operation_type:
                self.report_error(
                    GraphQLError(
                        duplicate_operation_type_message(operation.value),
                        [already_defined_operation_type, operation_type],
                    )
                )
            else:
                self.defined_operation_types[operation] = operation_type
        return self.SKIP

    enter_schema_definition = enter_schema_extension = check_operation_types
