"""Defer stream directive on root field rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from ...language import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationType,
)
from ...type import GraphQLDeferDirective, GraphQLStreamDirective
from . import ValidationRule

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
    """

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        operation = node.operation
        if operation not in (OperationType.SUBSCRIPTION, OperationType.MUTATION):
            return
        schema = self.context.schema
        root_type = schema.get_root_type(operation)
        if root_type:
            document = self.context.document
            fragments = {
                definition.name.value: definition
                for definition in document.definitions
                if isinstance(definition, FragmentDefinitionNode)
            }
            self.forbid_defer_stream(
                operation, root_type, fragments, node.selection_set, set()
            )

    def forbid_defer_stream(
        self,
        operation_type: OperationType,
        root_type: GraphQLObjectType,
        fragments: dict[str, FragmentDefinitionNode],
        selection_set: SelectionSetNode,
        visited_fragments: set[str],
    ) -> None:
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                stream = get_directive(selection, GraphQLStreamDirective.name)
                if stream:
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
                fragment = fragments.get(fragment_name)
                if fragment:
                    defer = get_directive(selection, GraphQLDeferDirective.name)
                    if defer:
                        self.report_error(
                            GraphQLError(
                                "Defer directive cannot be used on root"
                                f" {operation_type.value} type '{root_type.name}'.",
                                defer,
                            )
                        )
                    self.forbid_defer_stream(
                        operation_type,
                        root_type,
                        fragments,
                        fragment.selection_set,
                        visited_fragments,
                    )
                visited_fragments.add(fragment_name)
            elif isinstance(selection, InlineFragmentNode):
                defer = get_directive(selection, GraphQLDeferDirective.name)
                if defer:
                    self.report_error(
                        GraphQLError(
                            "Defer directive cannot be used on root"
                            f" {operation_type.value} type '{root_type.name}'.",
                            defer,
                        )
                    )
                self.forbid_defer_stream(
                    operation_type,
                    root_type,
                    fragments,
                    selection.selection_set,
                    visited_fragments,
                )
