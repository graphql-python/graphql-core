from typing import Dict, List, Union, cast

from ...error import GraphQLError
from ...language import DirectiveDefinitionNode, DirectiveNode, Node
from ...type import specified_directives
from . import ASTValidationRule, SDLValidationContext, ValidationContext

__all__ = ["UniqueDirectivesPerLocationRule", "duplicate_directive_message"]


def duplicate_directive_message(directive_name: str) -> str:
    return f"The directive '{directive_name}' can only be used once at this location."


class UniqueDirectivesPerLocationRule(ASTValidationRule):
    """Unique directive names per location

    A GraphQL document is only valid if all non-repeatable directives at a given
    location are uniquely named.
    """

    context: Union[ValidationContext, SDLValidationContext]

    def __init__(self, context: Union[ValidationContext, SDLValidationContext]) -> None:
        super().__init__(context)
        unique_directive_map: Dict[str, bool] = {}

        schema = context.schema
        defined_directives = (
            schema.directives if schema else cast(List, specified_directives)
        )
        for directive in defined_directives:
            unique_directive_map[directive.name] = not directive.is_repeatable
        ast_definitions = context.document.definitions
        for def_ in ast_definitions:
            if isinstance(def_, DirectiveDefinitionNode):
                unique_directive_map[def_.name.value] = not def_.repeatable
        self.unique_directive_map = unique_directive_map

    # Many different AST nodes may contain directives. Rather than listing them all,
    # just listen for entering any node, and check to see if it defines any directives.
    def enter(self, node: Node, *_args):
        directives: List[DirectiveNode] = getattr(node, "directives", None)
        if directives:
            known_directives: Dict[str, DirectiveNode] = {}
            for directive in directives:
                directive_name = directive.name.value

                if self.unique_directive_map.get(directive_name):
                    if directive_name in known_directives:
                        self.report_error(
                            GraphQLError(
                                duplicate_directive_message(directive_name),
                                [known_directives[directive_name], directive],
                            )
                        )
                    else:
                        known_directives[directive_name] = directive
