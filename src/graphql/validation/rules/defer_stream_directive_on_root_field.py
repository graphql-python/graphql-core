"""Defer stream directive on root field rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...error import GraphQLError
from ...language import (
    FieldNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationType,
)
from ...type import GraphQLDeferDirective, GraphQLStreamDirective
from . import ValidationContext, ValidationRule

if TYPE_CHECKING:
    from ...language import (
        DirectiveNode,
        OperationDefinitionNode,
        SelectionSetNode,
    )
    from ...type import GraphQLObjectType

__all__ = ["DeferStreamDirectiveOnRootField"]


def get_directive(
    node: FieldNode | FragmentSpreadNode | InlineFragmentNode, name: str
) -> DirectiveNode | None:
    for directive in node.directives or ():
        if directive.name.value == name:
            return directive
    return None


class DeferStreamDirectiveOnRootField(ValidationRule):
    """Defer and stream directives are used on valid root field

    A GraphQL document is only valid if defer directives are not used on root
    mutation or subscription types.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import DeferStreamDirectiveOnRootField
    >>> schema = build_schema(
    ...     'type Query { message: String } type Mutation { updateMessage: String }'
    ... )
    >>> document = parse('mutation { ... @defer { updateMessage } }')
    >>> errors = validate(schema, document, [DeferStreamDirectiveOnRootField])
    >>> print(errors[0].message)
    Defer directive cannot be used on root mutation type 'Mutation'.
    >>> document = parse('{ ... @defer { message } }')
    >>> validate(schema, document, [DeferStreamDirectiveOnRootField])
    []
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self.checked_fragments: set[str] = set()

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        operation = node.operation
        if operation not in (OperationType.SUBSCRIPTION, OperationType.MUTATION):
            return
        schema = self.context.schema
        root_type = schema.get_root_type(operation)
        if root_type:
            visited_fragments: set[str] = set()
            if self.forbid_defer_stream(
                operation, root_type, node.selection_set, visited_fragments
            ):
                self.checked_fragments.update(visited_fragments)

    def forbid_defer_stream(
        self,
        operation_type: OperationType,
        root_type: GraphQLObjectType,
        selection_set: SelectionSetNode,
        visited_fragments: set[str],
    ) -> bool:
        """Report defer and stream directives used on the root type.

        Returns whether no error was found.

        :meta private:
        """
        valid = True
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                stream = get_directive(selection, GraphQLStreamDirective.name)
                if stream:
                    valid = False
                    self.report_error(
                        GraphQLError(
                            "Stream directive cannot be used on root"
                            f" {operation_type.value} type '{root_type.name}'.",
                            stream,
                        )
                    )
            elif isinstance(selection, FragmentSpreadNode):
                fragment_name = selection.name.value
                if fragment_name in visited_fragments:
                    continue
                visited_fragments.add(fragment_name)
                fragment = self.context.get_fragment(fragment_name)
                if fragment:
                    defer = get_directive(selection, GraphQLDeferDirective.name)
                    if defer:
                        valid = False
                        self.report_error(
                            GraphQLError(
                                "Defer directive cannot be used on root"
                                f" {operation_type.value} type '{root_type.name}'.",
                                defer,
                            )
                        )
                    if fragment_name not in self.checked_fragments:
                        valid = (
                            self.forbid_defer_stream(
                                operation_type,
                                root_type,
                                fragment.selection_set,
                                visited_fragments,
                            )
                            and valid
                        )
            else:  # the only remaining selection kind is an inline fragment
                inline_fragment = cast("InlineFragmentNode", selection)
                defer = get_directive(inline_fragment, GraphQLDeferDirective.name)
                if defer:
                    valid = False
                    self.report_error(
                        GraphQLError(
                            "Defer directive cannot be used on root"
                            f" {operation_type.value} type '{root_type.name}'.",
                            defer,
                        )
                    )
                valid = (
                    self.forbid_defer_stream(
                        operation_type,
                        root_type,
                        inline_fragment.selection_set,
                        visited_fragments,
                    )
                    and valid
                )
        return valid
