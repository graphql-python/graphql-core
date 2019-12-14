from typing import Union, cast

from ...error import GraphQLError
from ...language import (
    DirectiveDefinitionNode,
    DocumentNode,
    ExecutableDefinitionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    TypeDefinitionNode,
)
from . import ASTValidationRule

__all__ = ["ExecutableDefinitionsRule"]


class ExecutableDefinitionsRule(ASTValidationRule):
    """Executable definitions

    A GraphQL document is only valid for execution if all definitions are either
    operation or fragment definitions.
    """

    def enter_document(self, node: DocumentNode, *_args):
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
                        f"The {def_name} definition is not executable.", definition,
                    )
                )
        return self.SKIP
