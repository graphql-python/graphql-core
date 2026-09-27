from typing import Any

from ...error import GraphQLError
from ...language import SchemaDefinitionNode
from . import SDLValidationRule, SDLValidationContext

__all__ = ["LoneSchemaDefinitionRule"]


class LoneSchemaDefinitionRule(SDLValidationRule):
    """Lone Schema definition

    A GraphQL document is only valid if it contains only one schema definition.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema
    >>> from graphql.validation import LoneSchemaDefinitionRule
    >>> from graphql.validation.specified_rules import specified_sdl_rules
    >>> LoneSchemaDefinitionRule in specified_sdl_rules
    True
    >>> sdl = (
    ...     'schema { query: Query } schema { query: Query }'
    ...     ' type Query { name: String }'
    ... )
    >>> build_schema(sdl)
    Traceback (most recent call last):
    ...
    TypeError: Must provide only one schema definition.
    There can be only one query type in schema.
    >>> sdl = 'schema { query: Query } type Query { name: String }'
    >>> schema = build_schema(sdl)
    """

    def __init__(self, context: SDLValidationContext):
        super().__init__(context)
        old_schema = context.schema
        self.already_defined = old_schema and (
            old_schema.ast_node
            or old_schema.query_type
            or old_schema.mutation_type
            or old_schema.subscription_type
        )
        self.schema_definitions_count = 0

    def enter_schema_definition(self, node: SchemaDefinitionNode, *_args: Any) -> None:
        """Called when entering a schema definition node.

        :meta private:
        """
        if self.already_defined:
            self.report_error(
                GraphQLError(
                    "Cannot define a new schema within a schema extension.", node
                )
            )
        else:
            if self.schema_definitions_count:
                self.report_error(
                    GraphQLError("Must provide only one schema definition.", node)
                )
            self.schema_definitions_count += 1
