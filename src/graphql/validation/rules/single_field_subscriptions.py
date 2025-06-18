"""Single field subscriptions rule"""

from __future__ import annotations

from typing import Any

from ...error import GraphQLError
from ...execution.collect_fields import FieldDetails, collect_fields
from ...language import (
    FieldNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from . import ValidationRule

__all__ = ["SingleFieldSubscriptionsRule"]


def to_nodes(field_details_list: list[FieldDetails]) -> list[FieldNode]:
    return [field_details.node for field_details in field_details_list]


class SingleFieldSubscriptionsRule(ValidationRule):
    """Subscriptions must only include a single non-introspection field.

    A GraphQL subscription is valid only if it contains a single root field and
    that root field is not an introspection field.

    See https://spec.graphql.org/draft/#sec-Single-root-field
    """

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        if node.operation != OperationType.SUBSCRIPTION:
            return
        schema = self.context.schema
        subscription_type = schema.subscription_type
        if subscription_type:
            operation_name = node.name.value if node.name else None
            variable_values: dict[str, Any] = {}
            document = self.context.document
            fragments: dict[str, FragmentDefinitionNode] = {
                definition.name.value: definition
                for definition in document.definitions
                if isinstance(definition, FragmentDefinitionNode)
            }
            fields = collect_fields(
                schema,
                fragments,
                variable_values,
                subscription_type,
                node,
            ).fields
            if len(fields) > 1:
                field_groups = list(fields.values())
                extra_field_groups = field_groups[1:]
                extra_field_selection = [
                    node
                    for field_group in extra_field_groups
                    for node in to_nodes(field_group)
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
            for field_group in fields.values():
                field_name = to_nodes(field_group)[0].name.value
                if field_name.startswith("__"):
                    self.report_error(
                        GraphQLError(
                            (
                                "Anonymous Subscription"
                                if operation_name is None
                                else f"Subscription '{operation_name}'"
                            )
                            + " must not select an introspection top level field.",
                            to_nodes(field_group),
                        )
                    )
