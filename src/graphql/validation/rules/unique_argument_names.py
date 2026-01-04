"""Unique argument names rule"""

from __future__ import annotations

from operator import attrgetter
from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from ...pyutils import group_by
from . import ASTValidationRule

if TYPE_CHECKING:
    from collections.abc import Collection

    from ...language import ArgumentNode, DirectiveNode, FieldNode

__all__ = ["UniqueArgumentNamesRule"]


class UniqueArgumentNamesRule(ASTValidationRule):
    """Unique argument names

    A GraphQL field or directive is only valid if all supplied arguments are uniquely
    named.

    See https://spec.graphql.org/draft/#sec-Argument-Names
    """

    def enter_field(self, node: FieldNode, *_args: Any) -> None:
        self.check_arg_uniqueness(node.arguments)

    def enter_directive(self, node: DirectiveNode, *_args: Any) -> None:
        self.check_arg_uniqueness(node.arguments)

    def check_arg_uniqueness(self, argument_nodes: Collection[ArgumentNode]) -> None:
        seen_args = group_by(argument_nodes, attrgetter("name.value"))

        for arg_name, arg_nodes in seen_args.items():
            if len(arg_nodes) > 1:
                self.report_error(
                    GraphQLError(
                        f"There can be only one argument named '{arg_name}'.",
                        [node.name for node in arg_nodes],
                    )
                )
