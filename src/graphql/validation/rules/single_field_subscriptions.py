"""Single field subscriptions rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from ...execution.collect_fields import (
    FieldDetailsList,
    FragmentDetails,
    collect_fields,
)
from ...execution.values import VariableValues
from ...language import (
    FieldNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from ...type import GraphQLDeferDirective
from . import ValidationContext, ValidationRule

if TYPE_CHECKING:
    from ...language import SelectionSetNode

__all__ = ["SingleFieldSubscriptionsRule"]


def to_nodes(field_details_list: FieldDetailsList) -> list[FieldNode]:
    return [field_details.node for field_details in field_details_list]


class SingleFieldSubscriptionsRule(ValidationRule):
    """Subscriptions must only include a single non-introspection field.

    A GraphQL subscription is valid only if it contains a single root field and
    that root field is not an introspection field.

    See https://spec.graphql.org/draft/#sec-Single-root-field

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import SingleFieldSubscriptionsRule
    >>> sdl = 'type Query { name: String } type Subscription { a: String b: String }'
    >>> schema = build_schema(sdl)
    >>> document = parse('subscription { a b }')
    >>> errors = validate(schema, document, [SingleFieldSubscriptionsRule])
    >>> print(errors[0].message)
    Anonymous Subscription must select only one top level field.
    >>> document = parse('subscription { a }')
    >>> validate(schema, document, [SingleFieldSubscriptionsRule])
    []
    """

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
        self._fragments: dict[str, FragmentDetails] | None = None

    def spend_selection_set_work(self, selection_set: SelectionSetNode) -> None:
        """Reserve traversal and directive work before visiting a selection set.

        :meta private:
        """
        spend_fragment_work = self.context.spend_fragment_work
        selections = selection_set.selections
        spend_fragment_work(len(selections))
        for selection in selections:
            directives = selection.directives
            if directives:
                spend_fragment_work(len(directives))
                defer = next(
                    (
                        directive
                        for directive in directives
                        if directive.name.value == GraphQLDeferDirective.name
                    ),
                    None,
                )
                if defer and defer.arguments:
                    spend_fragment_work(len(defer.arguments))

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering an operation definition node.

        :meta private:
        """
        if node.operation != OperationType.SUBSCRIPTION:
            return
        schema = self.context.schema
        subscription_type = schema.subscription_type
        if subscription_type:
            operation_name = node.name.value if node.name else None
            variable_values: VariableValues = VariableValues({}, {})
            fragments = self._fragments
            if fragments is None:
                fragments = self._fragments = {
                    definition.name.value: FragmentDetails(definition)
                    for definition in self.context.document.definitions
                    if isinstance(definition, FragmentDefinitionNode)
                }
            grouped_field_set, _new_defer_usages, forbidden_directive_instances = (
                collect_fields(
                    schema,
                    fragments,
                    variable_values,
                    subscription_type,
                    node,
                    self.context.hide_suggestions,
                    True,
                    self.spend_selection_set_work,
                )
            )
            if forbidden_directive_instances:
                self.report_error(
                    GraphQLError(
                        (
                            "Anonymous Subscription"
                            if operation_name is None
                            else f"Subscription '{operation_name}'"
                        )
                        + " must not use `@skip` or `@include` directives"
                        " in the top level selection.",
                        forbidden_directive_instances,
                    )
                )
                return
            if not grouped_field_set:
                self.report_error(
                    GraphQLError(
                        (
                            "Anonymous Subscription"
                            if operation_name is None
                            else f"Subscription '{operation_name}'"
                        )
                        + " must select one top level field.",
                        node.selection_set,
                    )
                )
            elif len(grouped_field_set) > 1:
                field_details_lists = list(grouped_field_set.values())
                extra_field_details_lists = field_details_lists[1:]
                extra_field_selection = [
                    node
                    for field_details_list in extra_field_details_lists
                    for node in to_nodes(field_details_list)
                ]
                self.report_error(
                    GraphQLError(
                        (
                            "Anonymous Subscription"
                            if operation_name is None
                            else f"Subscription '{operation_name}'"
                        )
                        + " must select only one top level field.",
                        extra_field_selection,
                    )
                )
            for field_details_list in grouped_field_set.values():
                field_name = to_nodes(field_details_list)[0].name.value
                if field_name.startswith("__"):
                    self.report_error(
                        GraphQLError(
                            (
                                "Anonymous Subscription"
                                if operation_name is None
                                else f"Subscription '{operation_name}'"
                            )
                            + " must not select an introspection top level field.",
                            to_nodes(field_details_list),
                        )
                    )
