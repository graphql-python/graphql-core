from typing import Dict

from ...error import GraphQLError
from ...language import NameNode, ArgumentNode
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueArgumentNamesRule", "duplicate_arg_message"]


def duplicate_arg_message(arg_name: str) -> str:
    return f"There can only be one argument named '{arg_name}'."


class UniqueArgumentNamesRule(ASTValidationRule):
    """Unique argument names

    A GraphQL field or directive is only valid if all supplied arguments are uniquely
    named.
    """

    def __init__(self, context: ASTValidationContext) -> None:
        super().__init__(context)
        self.known_arg_names: Dict[str, NameNode] = {}

    def enter_field(self, *_args):
        self.known_arg_names.clear()

    def enter_directive(self, *_args):
        self.known_arg_names.clear()

    def enter_argument(self, node: ArgumentNode, *_args):
        known_arg_names = self.known_arg_names
        arg_name = node.name.value
        if arg_name in known_arg_names:
            self.report_error(
                GraphQLError(
                    duplicate_arg_message(arg_name),
                    [known_arg_names[arg_name], node.name],
                )
            )
        else:
            known_arg_names[arg_name] = node.name
        return self.SKIP
