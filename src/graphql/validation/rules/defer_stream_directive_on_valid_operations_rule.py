"""Defer stream directive on valid operations rule"""

from __future__ import annotations

from typing import Any

from ...error import GraphQLError
from ...language import (
    ArgumentNode,
    BooleanValueNode,
    DirectiveNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    VariableNode,
)
from ...type import (
    GraphQLDeferDirective,
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
    GraphQLStreamDirective,
)
from . import ASTValidationRule

__all__ = ["DeferStreamDirectiveOnValidOperationsRule"]


def get_directive(node: Any, name: str) -> DirectiveNode | None:
    for directive in node.directives or ():
        if directive.name.value == name:
            return directive
    return None


def get_if_argument(node: DirectiveNode) -> ArgumentNode | None:
    for argument in node.arguments or ():
        if argument.name.value == "if":
            return argument
    return None


def if_argument_can_be_false(node: DirectiveNode) -> bool:
    # @defer(if: false) / @stream(if: false)
    # @defer(if: $shouldDefer) / @stream(if: $shouldStream)
    if_argument = get_if_argument(node)
    if not if_argument:
        return False
    if isinstance(if_argument.value, BooleanValueNode):
        if if_argument.value.value:
            return False
    elif not isinstance(if_argument.value, VariableNode):
        return False
    return True


def can_be_skipped_via_skip_directive(node: DirectiveNode) -> bool:
    # @skip(if: true)
    # @skip(if: $shouldSkip)
    if_argument = get_if_argument(node)
    if not if_argument:
        # Missing `if` is reported by ProvidedRequiredArgumentsRule. For this rule,
        # treat malformed @skip as potentially skipped to avoid duplicate errors.
        return True
    # If argument is a static boolean, it is always skipped if true,
    # never skipped if false; otherwise it can be skipped via a variable.
    if isinstance(if_argument.value, BooleanValueNode):
        return if_argument.value.value
    return True


def can_be_skipped_via_include_directive(node: DirectiveNode) -> bool:
    # @include(if: false)
    # @include(if: $shouldInclude)
    if_argument = get_if_argument(node)
    if not if_argument:
        # Missing `if` is reported by ProvidedRequiredArgumentsRule. For this rule,
        # treat malformed @include as not skippable.
        return False
    # If argument is a static boolean, it is always skipped if false,
    # never skipped if true; otherwise it can be skipped via a variable.
    if isinstance(if_argument.value, BooleanValueNode):
        return not if_argument.value.value
    return True


class DeferStreamDirectiveOnValidOperationsRule(ASTValidationRule):
    """Defer and stream directives are used on valid operations

    A GraphQL document is only valid if defer and stream directives are not used
    on root mutation or subscription types.
    """

    def enter_operation_definition(
        self, operation: OperationDefinitionNode, *_args: Any
    ) -> None:
        if operation.operation != OperationType.SUBSCRIPTION:
            return
        fragments: dict[str, FragmentDefinitionNode] = {}
        for definition in self.context.document.definitions:
            if isinstance(definition, FragmentDefinitionNode):
                fragments[definition.name.value] = definition
        self.forbid_unconditional_defer_stream(
            fragments, operation.selection_set, [], set()
        )

    def forbid_unconditional_defer_stream(
        self,
        fragments: dict[str, FragmentDefinitionNode],
        selection_set: SelectionSetNode,
        parent_nodes: list[FragmentSpreadNode],
        visited_fragments: set[str],
    ) -> None:
        for selection in selection_set.selections:
            skip = get_directive(selection, GraphQLSkipDirective.name)
            if skip and can_be_skipped_via_skip_directive(skip):
                continue
            include = get_directive(selection, GraphQLIncludeDirective.name)
            if include and can_be_skipped_via_include_directive(include):
                continue
            for directive in selection.directives or ():
                name = directive.name.value
                if name == GraphQLDeferDirective.name:
                    if if_argument_can_be_false(directive):
                        continue
                    msg = (
                        "Defer directive not supported on subscription operations."
                        " Disable `@defer` by setting the `if` argument to `false`."
                    )
                elif name == GraphQLStreamDirective.name:
                    if if_argument_can_be_false(directive):
                        continue
                    msg = (
                        "Stream directive not supported on subscription operations."
                        " Disable `@stream` by setting the `if` argument to `false`."
                    )
                else:
                    continue
                self.report_error(GraphQLError(msg, [directive, *parent_nodes]))
            if isinstance(selection, FragmentSpreadNode):
                fragment_name = selection.name.value
                if fragment_name in visited_fragments:
                    continue
                visited_fragments.add(fragment_name)
                fragment = fragments.get(fragment_name)
                if fragment:
                    self.forbid_unconditional_defer_stream(
                        fragments,
                        fragment.selection_set,
                        [selection, *parent_nodes],
                        visited_fragments,
                    )
            else:
                child_selection_set = getattr(selection, "selection_set", None)
                if child_selection_set:
                    self.forbid_unconditional_defer_stream(
                        fragments,
                        child_selection_set,
                        parent_nodes,
                        visited_fragments,
                    )
