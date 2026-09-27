from operator import attrgetter
from typing import Any, Collection

from ...error import GraphQLError
from ...language import ArgumentNode, DirectiveNode, FieldNode
from ...pyutils import group_by
from . import ASTValidationRule

__all__ = ["UniqueArgumentNamesRule"]


class UniqueArgumentNamesRule(ASTValidationRule):
    """Unique argument names

    A GraphQL field or directive is only valid if all supplied arguments are uniquely
    named.

    See https://spec.graphql.org/draft/#sec-Argument-Names

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import UniqueArgumentNamesRule
    >>> schema = build_schema('type Query { field(arg: String): String }')
    >>> document = parse('{ field(arg: "1", arg: "2") }')
    >>> errors = validate(schema, document, [UniqueArgumentNamesRule])
    >>> print(errors[0].message)
    There can be only one argument named 'arg'.
    >>> document = parse('{ field(arg: "1") }')
    >>> validate(schema, document, [UniqueArgumentNamesRule])
    []
    """

    def enter_field(self, node: FieldNode, *_args: Any) -> None:
        """Called when entering a field node.

        :meta private:
        """
        self.check_arg_uniqueness(node.arguments)

    def enter_directive(self, node: DirectiveNode, *args: Any) -> None:
        """Called when entering a directive node.

        :meta private:
        """
        self.check_arg_uniqueness(node.arguments)

    def check_arg_uniqueness(self, argument_nodes: Collection[ArgumentNode]) -> None:
        """Report arguments with the same name.

        :meta private:
        """
        seen_args = group_by(argument_nodes, attrgetter("name.value"))

        for arg_name, arg_nodes in seen_args.items():
            if len(arg_nodes) > 1:
                self.report_error(
                    GraphQLError(
                        f"There can be only one argument named '{arg_name}'.",
                        [node.name for node in arg_nodes],
                    )
                )
