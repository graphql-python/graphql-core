"""Unique input field names rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from . import ASTValidationContext, ASTValidationRule

if TYPE_CHECKING:
    from ...language import NameNode, ObjectFieldNode

__all__ = ["UniqueInputFieldNamesRule"]


class UniqueInputFieldNamesRule(ASTValidationRule):
    """Unique input field names

    A GraphQL input object value is only valid if all supplied fields are uniquely
    named.

    See https://spec.graphql.org/draft/#sec-Input-Object-Field-Uniqueness
    """

    def __init__(self, context: ASTValidationContext) -> None:
        super().__init__(context)
        self.known_names_stack: list[dict[str, NameNode]] = []
        self.known_names: dict[str, NameNode] = {}

    def enter_object_value(self, *_args: Any) -> None:
        self.known_names_stack.append(self.known_names)
        self.known_names = {}

    def leave_object_value(self, *_args: Any) -> None:
        self.known_names = self.known_names_stack.pop()

    def enter_object_field(self, node: ObjectFieldNode, *_args: Any) -> None:
        known_names = self.known_names
        field_name = node.name.value
        if field_name in known_names:
            self.report_error(
                GraphQLError(
                    f"There can be only one input field named '{field_name}'.",
                    [known_names[field_name], node.name],
                )
            )
        else:
            known_names[field_name] = node.name
