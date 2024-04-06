"""Unique fragment names rule"""

from __future__ import annotations

from typing import Any

from ...error import GraphQLError
from ...language import SKIP, FragmentDefinitionNode, NameNode, VisitorAction
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueFragmentNamesRule"]


class UniqueFragmentNamesRule(ASTValidationRule):
    """Unique fragment names

    A GraphQL document is only valid if all defined fragments have unique names.

    See https://spec.graphql.org/draft/#sec-Fragment-Name-Uniqueness
    """

    def __init__(self, context: ASTValidationContext) -> None:
        super().__init__(context)
        self.known_fragment_names: dict[str, NameNode] = {}

    @staticmethod
    def enter_operation_definition(*_args: Any) -> VisitorAction:
        return SKIP

    def enter_fragment_definition(
        self, node: FragmentDefinitionNode, *_args: Any
    ) -> VisitorAction:
        known_fragment_names = self.known_fragment_names
        fragment_name = node.name.value
        if fragment_name in known_fragment_names:
            self.report_error(
                GraphQLError(
                    f"There can be only one fragment named '{fragment_name}'.",
                    [known_fragment_names[fragment_name], node.name],
                )
            )
        else:
            known_fragment_names[fragment_name] = node.name
        return SKIP
