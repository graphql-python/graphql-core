from typing import List

from ...error import GraphQLError
from ...language import SchemaDefinitionNode
from . import SDLValidationRule, SDLValidationContext

__all__ = [
    'LoneSchemaDefinition',
    'schema_definition_alone_message', 'cannot_define_schema_within_extension']


def schema_definition_alone_message():
    return 'Must provide only one schema definition.'


def cannot_define_schema_within_extension():
    return 'Cannot define a new schema within a schema extension.'


class LoneSchemaDefinition(SDLValidationRule):
    """Lone Schema definition

    A GraphQL document is only valid if it contains only one schema definition.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        old_schema = context.schema
        self.already_defined = old_schema and (
            old_schema.ast_node or old_schema.query_type or
            old_schema.mutation_type or old_schema.subscription_type)
        self.schema_nodes: List[SchemaDefinitionNode] = []

    def enter_schema_definition(self, node: SchemaDefinitionNode, *_args):
        if self.already_defined:
            self.report_error(GraphQLError(
                cannot_define_schema_within_extension(), [node]))
        else:
            self.schema_nodes.append(node)

    def leave_document(self, *_args):
        if len(self.schema_nodes) > 1:
            self.report_error(GraphQLError(
                schema_definition_alone_message(), self.schema_nodes))
