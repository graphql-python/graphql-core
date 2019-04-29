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

__all__ = ["ExecutableDefinitionsRule", "non_executable_definitions_message"]


def non_executable_definitions_message(def_name: str) -> str:
    return f"The {def_name} definition is not executable."


class ExecutableDefinitionsRule(ASTValidationRule):
    """Executable definitions

    A GraphQL document is only valid for execution if all definitions are either
    operation or fragment definitions.
    """

    def enter_document(self, node: DocumentNode, *_args):
        for definition in node.definitions:
            if not isinstance(definition, ExecutableDefinitionNode):
                self.report_error(
                    GraphQLError(
                        non_executable_definitions_message(
                            "schema"
                            if isinstance(
                                definition, (SchemaDefinitionNode, SchemaExtensionNode)
                            )
                            else cast(
                                Union[DirectiveDefinitionNode, TypeDefinitionNode],
                                definition,
                            ).name.value
                        ),
                        definition,
                    )
                )
        return self.SKIP
