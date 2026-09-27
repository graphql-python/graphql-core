"""Stream directive on list field rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...error import GraphQLError
from ...type import GraphQLStreamDirective, is_list_type, is_wrapping_type
from . import ASTValidationRule, ValidationContext

if TYPE_CHECKING:
    from ...language import DirectiveNode, Node

__all__ = ["StreamDirectiveOnListField"]


class StreamDirectiveOnListField(ASTValidationRule):
    """Stream directives are used on list fields

    A GraphQL document is only valid if stream directives are used on list fields.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import StreamDirectiveOnListField
    >>> schema = build_schema('type Query { name: String friends: [String] }')
    >>> document = parse('{ name @stream(initialCount: 0) }')
    >>> errors = validate(schema, document, [StreamDirectiveOnListField])
    >>> print(errors[0].message)
    Stream directive cannot be used on non-list field 'name' on type 'Query'.
    >>> document = parse('{ friends @stream(initialCount: 0) }')
    >>> validate(schema, document, [StreamDirectiveOnListField])
    []
    """

    def enter_directive(
        self,
        node: DirectiveNode,
        _key: Any,
        _parent: Any,
        _path: Any,
        _ancestors: list[Node],
    ) -> None:
        """Called when entering a directive node.

        :meta private:
        """
        context = cast("ValidationContext", self.context)
        field_def = context.get_field_def()
        parent_type = context.get_parent_type()
        if (
            field_def
            and parent_type
            and node.name.value == GraphQLStreamDirective.name
            and not (
                is_list_type(field_def.type)
                or (
                    is_wrapping_type(field_def.type)
                    and is_list_type(field_def.type.of_type)
                )
            )
        ):
            try:
                field_name = next(
                    name
                    for name, field in parent_type.fields.items()  # type: ignore
                    if field is field_def
                )
            except StopIteration:  # pragma: no cover
                field_name = ""
            else:
                field_name = f" '{field_name}'"
            self.report_error(
                GraphQLError(
                    "Stream directive cannot be used on non-list"
                    f" field{field_name} on type '{parent_type.name}'.",
                    node,
                )
            )
