"""Executable definitions rule"""

from typing import Any, Union, cast

from ...error import GraphQLError
from ...language import (
    DirectiveDefinitionNode,
    DocumentNode,
    ExecutableDefinitionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    TypeDefinitionNode,
    VisitorAction,
    SKIP,
)
from . import ASTValidationRule

__all__ = ["ExecutableDefinitionsRule"]


class ExecutableDefinitionsRule(ASTValidationRule):
    """Executable definitions

    A GraphQL document is only valid for execution if all definitions are either
    operation or fragment definitions.

    See https://spec.graphql.org/draft/#sec-Executable-Definitions

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import ExecutableDefinitionsRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('type Extra { field: String }')
    >>> errors = validate(schema, document, [ExecutableDefinitionsRule])
    >>> print(errors[0].message)
    The 'Extra' definition is not executable.
    >>> document = parse('{ name }')
    >>> validate(schema, document, [ExecutableDefinitionsRule])
    []
    """

    def enter_document(self, node: DocumentNode, *_args: Any) -> VisitorAction:
        """Called when entering a document node.

        :meta private:
        """
        for definition in node.definitions:
            if not isinstance(definition, ExecutableDefinitionNode):
                def_name = (
                    "schema"
                    if isinstance(
                        definition, (SchemaDefinitionNode, SchemaExtensionNode)
                    )
                    else "'{}'".format(
                        cast(
                            Union[DirectiveDefinitionNode, TypeDefinitionNode],
                            definition,
                        ).name.value
                    )
                )
                self.report_error(
                    GraphQLError(
                        f"The {def_name} definition is not executable.",
                        definition,
                    )
                )
        return SKIP
