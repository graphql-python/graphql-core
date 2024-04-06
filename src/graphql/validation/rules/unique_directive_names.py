"""Unique directive names rule"""

from __future__ import annotations

from typing import Any

from ...error import GraphQLError
from ...language import SKIP, DirectiveDefinitionNode, NameNode, VisitorAction
from . import SDLValidationContext, SDLValidationRule

__all__ = ["UniqueDirectiveNamesRule"]


class UniqueDirectiveNamesRule(SDLValidationRule):
    """Unique directive names

    A GraphQL document is only valid if all defined directives have unique names.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        self.known_directive_names: dict[str, NameNode] = {}
        self.schema = context.schema

    def enter_directive_definition(
        self, node: DirectiveDefinitionNode, *_args: Any
    ) -> VisitorAction:
        directive_name = node.name.value

        if self.schema and self.schema.get_directive(directive_name):
            self.report_error(
                GraphQLError(
                    f"Directive '@{directive_name}' already exists in the schema."
                    " It cannot be redefined.",
                    node.name,
                )
            )
        else:
            if directive_name in self.known_directive_names:
                self.report_error(
                    GraphQLError(
                        f"There can be only one directive named '@{directive_name}'.",
                        [self.known_directive_names[directive_name], node.name],
                    )
                )
            else:
                self.known_directive_names[directive_name] = node.name
            return SKIP

        return None
