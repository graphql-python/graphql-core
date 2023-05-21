from typing import Any, List, cast

from ...error import GraphQLError
from ...language import DirectiveNode, Node
from ...type import GraphQLDeferDirective, GraphQLStreamDirective
from . import ASTValidationRule, ValidationContext


__all__ = ["DeferStreamDirectiveOnRootField"]


class DeferStreamDirectiveOnRootField(ASTValidationRule):
    """Defer and stream directives are used on valid root field

    A GraphQL document is only valid if defer directives are not used on root
    mutation or subscription types.
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
        parent_type = context.get_parent_type()
        if not parent_type:
            return
        schema = context.schema
        mutation_type = schema.mutation_type
        subscription_type = schema.subscription_type

        if node.name.value == GraphQLDeferDirective.name:
            if mutation_type and parent_type is mutation_type:
                self.report_error(
                    GraphQLError(
                        "Defer directive cannot be used on root"
                        f" mutation type '{parent_type.name}'.",
                        node,
                    )
                )
            if subscription_type and parent_type is subscription_type:
                self.report_error(
                    GraphQLError(
                        "Defer directive cannot be used on root"
                        f" subscription type '{parent_type.name}'.",
                        node,
                    )
                )
        if node.name.value == GraphQLStreamDirective.name:
            if mutation_type and parent_type is mutation_type:
                self.report_error(
                    GraphQLError(
                        "Stream directive cannot be used on root"
                        f" mutation type '{parent_type.name}'.",
                        node,
                    )
                )
            if subscription_type and parent_type is subscription_type:
                self.report_error(
                    GraphQLError(
                        "Stream directive cannot be used on root"
                        f" subscription type '{parent_type.name}'.",
                        node,
                    )
                )
