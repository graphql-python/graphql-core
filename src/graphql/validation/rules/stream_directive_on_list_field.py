from typing import Any, List, cast

from ...error import GraphQLError
from ...language import DirectiveNode, Node
from ...type import GraphQLStreamDirective, is_list_type, is_wrapping_type
from . import ASTValidationRule, ValidationContext


__all__ = ["StreamDirectiveOnListField"]


class StreamDirectiveOnListField(ASTValidationRule):
    """Stream directive on list field

    A GraphQL document is only valid if stream directives are used on list fields.
    """

    def enter_directive(
        self,
        node: DirectiveNode,
        _key: Any,
        _parent: Any,
        _path: Any,
        _ancestors: List[Node],
    ) -> None:
        context = cast(ValidationContext, self.context)
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
