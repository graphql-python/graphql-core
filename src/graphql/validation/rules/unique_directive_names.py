from typing import Dict

from ...error import GraphQLError
from ...language import NameNode, DirectiveDefinitionNode
from . import SDLValidationContext, SDLValidationRule

__all__ = [
    "UniqueDirectiveNamesRule",
    "duplicate_directive_name_message",
    "existed_directive_name_message",
]


def duplicate_directive_name_message(directive_name: str) -> str:
    return f"There can be only one directive named '{directive_name}'."


def existed_directive_name_message(directive_name: str) -> str:
    return (
        f"Directive '{directive_name}' already exists in the schema."
        " It cannot be redefined."
    )


class UniqueDirectiveNamesRule(SDLValidationRule):
    """Unique directive names

    A GraphQL document is only valid if all defined directives have unique names.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        self.known_directive_names: Dict[str, NameNode] = {}
        self.schema = context.schema

    def enter_directive_definition(self, node: DirectiveDefinitionNode, *_args):
        directive_name = node.name.value

        if self.schema and self.schema.get_directive(directive_name):
            self.report_error(
                GraphQLError(existed_directive_name_message(directive_name), node.name)
            )
        else:
            if directive_name in self.known_directive_names:
                self.report_error(
                    GraphQLError(
                        duplicate_directive_name_message(directive_name),
                        [self.known_directive_names[directive_name], node.name],
                    )
                )
            else:
                self.known_directive_names[directive_name] = node.name
            return self.SKIP
