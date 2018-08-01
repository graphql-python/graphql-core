from ...error import GraphQLError
from ...language import (
    FragmentDefinitionNode, OperationDefinitionNode,
    SchemaDefinitionNode, SchemaExtensionNode)
from . import ValidationRule

__all__ = ['ExecutableDefinitionsRule', 'non_executable_definitions_message']


def non_executable_definitions_message(def_name: str) -> str:
    return f'The {def_name} definition is not executable.'


class ExecutableDefinitionsRule(ValidationRule):
    """Executable definitions

    A GraphQL document is only valid for execution if all definitions are
    either operation or fragment definitions.
    """

    def enter_document(self, node, *_args):
        for definition in node.definitions:
            if not isinstance(definition, (
                    OperationDefinitionNode, FragmentDefinitionNode)):
                self.report_error(GraphQLError(
                    non_executable_definitions_message(
                        'schema' if isinstance(definition, (
                            SchemaDefinitionNode, SchemaExtensionNode))
                        else definition.name.value), [definition]))
        return self.SKIP
